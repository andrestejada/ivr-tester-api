"""IVR State Machine — Máquina de estados para procesar flujos IVR dinámicamente.

Arquitectura:
- Un único bucle continuo escucha el ASR
- Mantiene un índice del step actual (current_step_index)
- Acumula el transcript completo de la llamada
- Al hacer match con el step actual, recorta ese fragmento e itera
- Maneja timeouts por step (si no hace match en X segundos, falla)
- Soporta steps sin action (ej: bienvenida, despedida)
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from time import time
from dataclasses import dataclass, field
from typing import Callable
import hashlib

from src.infrastructure.logger import get_logger

logger = get_logger(__name__)

# Timeouts y thresholds
STEP_TIMEOUT_SECONDS = 20.0  # Máximo tiempo esperando el texto de un step
SILENCE_THRESHOLD_SECONDS = 5.0  # Silencio de 5s indica fin del step (no hay más opciones)
EARLY_EXIT_SILENCE_SECONDS = 1.0
STREAM_POLL_SECONDS = 0.5
SIMILARITY_THRESHOLD = 0.80  # 80% - evaluación final
EARLY_EXIT_THRESHOLD = 0.85  # 85% - early exit trigger


@dataclass
class StepMatchResult:
    """Resultado cuando se detecta un match de step."""
    
    matched: bool
    step_index: int
    matched_text: str  # Fragmento que hizo match
    action_to_execute: str | None  # Action del step (puede ser None)
    full_transcript_accumulated: str  # Transcript global hasta este punto
    confidence: Decimal


@dataclass
class IVRStateMachineState:
    """Estado interno de la máquina."""
    
    current_step_index: int = 0
    full_call_transcript: str = ""
    transcript_parts: list[str] = field(default_factory=list)
    current_partial: str = ""
    last_text_time: float = field(default_factory=time)
    step_start_time: float = field(default_factory=time)
    transcript_final_event: asyncio.Event = field(default_factory=asyncio.Event)
    early_match_found: bool = False
    previous_step_transcript: str = ""  # Transcripción anterior del step actual (para detectar repeticiones)
    last_evaluated_text: str = ""  # Cache para evitar re-evaluar el mismo texto (reduce DEBUG logs)
    last_match_result: 'StepMatchResult | None' = None  # Cache del ultimo resultado de match


class IVRStateMachine:
    """Máquina de estados para procesar flujos IVR en tiempo real.
    
    Características:
    - Escucha continua del stream de audio
    - Evaluación dinámica de steps
    - Timeout por step
    - Registro de transcript global
    - Soporte para steps sin action (passive listening)
    """
    
    def __init__(
        self, 
        flow_script: list[dict],
        evaluate_transcription_fn: Callable[[str, str, float], tuple[float, Decimal, bool]],
    ):
        """
        Args:
            flow_script: Lista de steps del formato:
                [
                    {"step": 1, "listen": "Welcome to...", "action": "1"},
                    {"step": 2, "listen": "What is your...", "action": None},  # Sin action
                    ...
                ]
            evaluate_transcription_fn: Función para evaluar similitud entre textos.
                                      Signature: (expected, transcribed, threshold) -> (ratio, confidence, is_match)
        """
        self.flow_script = flow_script
        self.evaluate_transcription_fn = evaluate_transcription_fn
        self.state = IVRStateMachineState()
        # Cache para resultados de evaluación de transcripción
        # Clave: hash(expected_text, current_full_text, threshold)
        # Valor: (ratio, confidence, is_match)
        self._evaluation_cache: dict[str, tuple[float, Decimal, bool]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_current_step(self) -> dict | None:
        """Obtiene el step actual."""
        if 0 <= self.state.current_step_index < len(self.flow_script):
            return self.flow_script[self.state.current_step_index]
        return None
    
    def is_flow_complete(self) -> bool:
        """¿Hemos procesado todos los steps?"""
        return self.state.current_step_index >= len(self.flow_script)
    
    def get_elapsed_time_current_step(self) -> float:
        """Tiempo transcurrido esperando el step actual."""
        return time() - self.state.step_start_time
    
    def accumulate_transcript_text(self, text: str, is_final: bool, speech_final: bool = False) -> None:
        """Acumula texto del ASR en la máquina de estados.
        
        Args:
            text: Fragmento de texto transcrito
            is_final: Si el ASR marca como transcripción final
            speech_final: Si el ASR detectó fin de habla (endpointing)
        """
        if text:
            self.state.last_text_time = time()
        
        if is_final:
            if text:
                self.state.transcript_parts.append(text)
            self.state.current_partial = ""
            if speech_final:
                self.state.transcript_final_event.set()
        else:
            if text:
                self.state.current_partial = text
    
    def get_full_text_buffer(self) -> str:
        """Retorna el texto acumulado hasta ahora (partes finales + parcial)."""
        current_full_text = " ".join(self.state.transcript_parts)
        if self.state.current_partial:
            current_full_text += (" " + self.state.current_partial)
        return current_full_text.strip()
    
    def _create_cache_key(self, expected: str, current: str, threshold: float) -> str:
        """Create a deterministic cache key for a transcription evaluation request.
        
        Uses SHA256 to create a compact, deterministic key.
        """
        combined = f"{expected}|{current}|{threshold}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _get_cached_evaluation(
        self, expected: str, current: str, threshold: float
    ) -> tuple[float, Decimal, bool] | None:
        """Check if evaluation result is cached. Returns result or None if not cached."""
        cache_key = self._create_cache_key(expected, current, threshold)
        if cache_key in self._evaluation_cache:
            self._cache_hits += 1
            return self._evaluation_cache[cache_key]
        self._cache_misses += 1
        return None
    
    def _cache_evaluation_result(
        self, expected: str, current: str, threshold: float,
        result: tuple[float, Decimal, bool]
    ) -> None:
        """Cache an evaluation result. Implements simple size limit (max 1000 entries)."""
        cache_key = self._create_cache_key(expected, current, threshold)
        
        # Simple eviction: if cache is full, clear it
        if len(self._evaluation_cache) >= 1000:
            self._evaluation_cache.clear()
            logger.debug("Evaluation cache full (1000 entries), cleared")
        
        self._evaluation_cache[cache_key] = result
    
    def get_cache_stats(self) -> dict:
        """Return cache statistics for monitoring."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._evaluation_cache),
            "hit_rate_percent": round(hit_rate, 2),
        }
    
    def check_for_step_match(self) -> StepMatchResult | None:
        """Evalúa si el texto acumulado hace match con el step actual.
        
        Retorna StepMatchResult si hay match, None en caso contrario.
        """
        current_step = self.get_current_step()
        if current_step is None:
            return None
        
        step_number = current_step.get("step", self.state.current_step_index + 1)
        expected_text = current_step.get("listen", "")
        action = current_step.get("action")
        
        if not expected_text:
            logger.warning(f"Step {step_number}: 'listen' field is empty")
            return None
        
        current_full_text = self.get_full_text_buffer()
        
        if not current_full_text:
            return None  # Sin texto aún
        
        # Try to get cached evaluation result first
        cached_result = self._get_cached_evaluation(
            expected_text,
            current_full_text,
            EARLY_EXIT_THRESHOLD
        )
        
        if cached_result is not None:
            ratio, confidence, is_match = cached_result
            logger.debug(
                f"Step {step_number}: Cache HIT | expected='{expected_text}' | "
                f"confidence={confidence}% | hit_rate={self.get_cache_stats()['hit_rate_percent']}%"
            )
        else:
            # Evaluamos con umbral de early exit
            ratio, confidence, is_match = self.evaluate_transcription_fn(
                expected_text,
                current_full_text,
                threshold=EARLY_EXIT_THRESHOLD
            )
            # Cache the result
            self._cache_evaluation_result(expected_text, current_full_text, EARLY_EXIT_THRESHOLD, (ratio, confidence, is_match))
        
        if is_match:
            logger.info(
                f"Step {step_number}: ✓ MATCH DETECTED | expected='{expected_text}' | got='{current_full_text}' | "
                f"confidence={confidence}% | action={action or 'None (passive)'}"
            )
            
            # Retornar el match con el fragmento específico que hizo match
            return StepMatchResult(
                matched=True,
                step_index=self.state.current_step_index,
                matched_text=current_full_text,  # Este será el texto que guardamos en el log
                action_to_execute=action,
                full_transcript_accumulated=self._build_global_transcript(),
                confidence=confidence,
            )
        
        return None
    
    def check_step_timeout(self) -> bool:
        """¿Se excedió el timeout esperando este step?"""
        elapsed = self.get_elapsed_time_current_step()
        if elapsed >= STEP_TIMEOUT_SECONDS:
            current_step = self.get_current_step()
            step_number = current_step.get("step") if current_step else self.state.current_step_index + 1
            logger.warning(
                f"Step {step_number}: ✗ TIMEOUT EXCEEDED ({elapsed:.1f}s >= {STEP_TIMEOUT_SECONDS}s). "
                f"Expected text: '{current_step.get('listen') if current_step else '?'}'"
            )
            return True
        return False
    
    def get_silence_duration(self) -> float:
        """Retorna cuántos segundos hace que no hay habla nueva.
        
        Útil para detectar pausas entre opciones del IVR.
        """
        if not self.state.transcript_parts and not self.state.current_partial:
            return 0.0
        return time() - self.state.last_text_time
    
    def check_if_step_repeated(self, current_text: str, repeat_threshold: float = 0.50) -> bool:
        """Detecta si el IVR está repitiendo el mismo menú.
        
        Si la transcripción actual tiene una similitud >= repeat_threshold con la
        transcripción anterior del step, significa que el IVR está leyendo lo mismo
        de nuevo (probablemente porque ninguna opción hizo match).
        
        Args:
            current_text: Texto actual acumulado del step
            repeat_threshold: Umbral de similitud para considerar como repetición (ej: 0.50 = 50%)
            
        Returns:
            True si se detecta repetición, False en caso contrario
        """
        if not self.state.previous_step_transcript:
            # Primera vez en este step, no hay referencia anterior
            return False
        
        # Comparar similitud entre transcripción actual y la anterior
        ratio = SequenceMatcher(None, self.state.previous_step_transcript, current_text).ratio()
        
        if ratio >= repeat_threshold:
            logger.warning(
                f"Step {self.state.current_step_index + 1}: ⚠ REPETITION DETECTED | "
                f"current_text='{current_text[:50]}...' | previous='{self.state.previous_step_transcript[:50]}...' | "
                f"similarity={ratio*100:.1f}% (threshold={repeat_threshold*100:.1f}%)"
            )
            return True
        
        return False
    
    def advance_to_next_step(self, matched_text: str) -> None:
        """Avanza la máquina de estados al siguiente step.
        
        Args:
            matched_text: Texto que fue reconocido (para actualizar transcript global)
        """
        # 1. Actualizar transcript global (apenas identificamos el match)
        self.state.full_call_transcript += matched_text + " "
        
        # 2. Guardar la transcripción actual como referencia para detectar repeticiones
        current_full_text = self.get_full_text_buffer()
        self.state.previous_step_transcript = current_full_text
        
        # 3. Avanzar al siguiente step
        self.state.current_step_index += 1
        
        # 4. Resetear estado para nuevo step
        self.state.transcript_parts = []  # Limpiar parts (opcionalmente, depende de si queremos preservar)
        self.state.current_partial = ""
        self.state.step_start_time = time()
        self.state.last_text_time = time()
        self.state.transcript_final_event.clear()
        self.state.early_match_found = False
        
        current_step = self.get_current_step()
        if current_step:
            step_number = current_step.get("step", self.state.current_step_index + 1)
            logger.info(f"Step {step_number}: ═ STATE TRANSITION ═ Moved to step #{self.state.current_step_index}")
    
    def clear_buffer_for_new_step(self) -> None:
        """Limpia el buffer de transcripción para empezar a escuchar un nuevo step.
        
        Esto es importante para evitar que audio residual del step anterior
        interfiera con la detección del siguiente step.
        """
        self.state.transcript_parts = []
        self.state.current_partial = ""
    
    def _build_global_transcript(self) -> str:
        """Construye el transcript global acumulado."""
        return self.state.full_call_transcript + " ".join(self.state.transcript_parts)
    
    def finalize_and_get_full_transcript(self, additional_text: str = "") -> str:
        """Finaliza la máquina de estados y retorna el transcript completo de la llamada.
        
        Args:
            additional_text: Texto adicional a agregar (ej: mensajes finales del IVR)
            
        Returns:
            Transcript completo de la llamada
        """
        final_transcript = self.state.full_call_transcript
        if " ".join(self.state.transcript_parts):
            final_transcript += " " + " ".join(self.state.transcript_parts)
        if self.state.current_partial:
            final_transcript += " " + self.state.current_partial
        if additional_text:
            final_transcript += " " + additional_text
        
        return final_transcript.strip()
