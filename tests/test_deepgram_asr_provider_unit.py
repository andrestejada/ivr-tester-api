"""Pruebas unitarias para DeepgramASRProvider.

Valida los Criterios de Aceptación (AC) de la HU-25:
- AC 1: Inicialización con variable de entorno (sin hardcodeo)
- AC 2: Transcripción mediante Streaming (WebSockets)
- AC 3: Política de resiliencia y reintentos (máximo 3)
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.config import Settings
from src.infrastructure.providers.deepgram_asr_provider import DeepgramASRProvider


class TestDeepgramASRProviderInitialization:
    """Pruebas de inicialización (AC 1: Variable de entorno)."""

    def test_init_with_valid_api_key(self) -> None:
        """AC 1: Inicialización correcta con API Key configurada."""
        settings = Settings(
            app_env="test",
            app_port=8000,
            base_url="http://localhost:8000",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            supabase_db_url="postgresql://test",
            supabase_jwt_secret="test-secret",
            deepgram_api_key="test-api-key-valid",
        )
        
        provider = DeepgramASRProvider(settings=settings)
        assert provider.settings.deepgram_api_key == "test-api-key-valid"

    def test_init_fails_without_api_key(self) -> None:
        """AC 1: Falla si deepgram_api_key no está configurada."""
        # Crear settings sin deepgram_api_key válida
        with pytest.raises(ValueError) as exc_info:
            # Intentar crear sin pasar una API key válida
            DeepgramASRProvider(
                settings=MagicMock(
                    deepgram_api_key=None,
                    spec=Settings
                )
            )
        
        assert "DEEPGRAM_API_KEY no está configurada" in str(exc_info.value)

    def test_init_fails_with_placeholder_api_key(self) -> None:
        """AC 1: Falla si deepgram_api_key es "placeholder"."""
        with pytest.raises(ValueError) as exc_info:
            DeepgramASRProvider(
                settings=MagicMock(
                    deepgram_api_key="placeholder",
                    spec=Settings
                )
            )
        
        assert "DEEPGRAM_API_KEY no está configurada" in str(exc_info.value)


class TestDeepgramASRProviderStreaming:
    """Pruebas de streaming (AC 2: WebSockets y callbacks)."""

    @pytest.fixture
    def valid_settings(self) -> Settings:
        """Settings con API Key válida para los tests."""
        return Settings(
            app_env="test",
            app_port=8000,
            base_url="http://localhost:8000",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            supabase_db_url="postgresql://test",
            supabase_jwt_secret="test-secret",
            deepgram_api_key="test-api-key-valid",
        )

    @pytest.mark.asyncio
    async def test_connect_establishes_deepgram_connection(
        self, valid_settings: Settings
    ) -> None:
        """AC 2: connect() inicia una conexión WebSocket con Deepgram."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        # Mock del AsyncDeepgramClient y su método listen.v1.connect()
        with patch(
            "src.infrastructure.providers.deepgram_asr_provider.AsyncDeepgramClient"
        ) as mock_client_class:
            mock_live_connection = AsyncMock()
            mock_live_connection.start_listening = AsyncMock()
            mock_live_connection.on = MagicMock(return_value=None)
            
            mock_connection_ctx = AsyncMock()
            mock_connection_ctx.__aenter__.return_value = mock_live_connection

            mock_client_instance = MagicMock()
            mock_client_instance.listen.v1.connect.return_value = mock_connection_ctx
            mock_client_class.return_value = mock_client_instance
            
            # Llamar a connect
            await provider.connect()
            
            # Verificaciones
            mock_client_class.assert_called_once_with(
                api_key="test-api-key-valid"
            )
            mock_client_instance.listen.v1.connect.assert_called_once()
            mock_live_connection.start_listening.assert_called_once()
            assert provider._is_connected is True

    @pytest.mark.asyncio
    async def test_send_audio_transmits_to_deepgram(
        self, valid_settings: Settings
    ) -> None:
        """AC 2: send_audio() envía bytes al WebSocket de Deepgram."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        with patch(
            "src.infrastructure.providers.deepgram_asr_provider.AsyncDeepgramClient"
        ) as mock_client_class:
            mock_live_connection = AsyncMock()
            mock_live_connection.start_listening = AsyncMock()
            mock_live_connection.send_media = AsyncMock()
            mock_live_connection.on = MagicMock(return_value=None)
            
            mock_connection_ctx = AsyncMock()
            mock_connection_ctx.__aenter__.return_value = mock_live_connection

            mock_client_instance = MagicMock()
            mock_client_instance.listen.v1.connect.return_value = mock_connection_ctx
            mock_client_class.return_value = mock_client_instance
            
            await provider.connect()
            
            # Enviar audio
            audio_chunk = b"\x00\x01\x02\x03"
            await provider.send_audio(audio_chunk)
            
            # Verificar que se envió al WebSocket
            mock_live_connection.send_media.assert_called_once_with(audio_chunk)

    @pytest.mark.asyncio
    async def test_set_transcript_handler_registers_callback(
        self, valid_settings: Settings
    ) -> None:
        """AC 2: set_transcript_handler() registra el callback correctamente."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        # Crear un callback mock
        mock_callback = AsyncMock()
        
        await provider.set_transcript_handler(mock_callback)
        
        # Verificar que el callback fue asignado
        assert provider._transcript_handler is mock_callback

    @pytest.mark.asyncio
    async def test_transcript_callback_invoked_with_text_and_is_final(
        self, valid_settings: Settings, caplog
    ) -> None:
        """AC 2: El callback es invocado con (texto, es_final) cuando Deepgram emite.
        
        Simula un evento TranscriptResponse de Deepgram con un fragmento parcial
        seguido de un fragmento final.
        """
        provider = DeepgramASRProvider(settings=valid_settings)
        
        # Mock de callback para capturar las llamadas
        mock_callback = AsyncMock()
        await provider.set_transcript_handler(mock_callback)
        
        # Simular evento de transcripción (fragmento parcial)
        mock_transcript = MagicMock()
        mock_transcript.is_final = False
        
        mock_alternative = MagicMock()
        mock_alternative.transcript = "Hola mundo"
        
        mock_channel = MagicMock()
        mock_channel.alternatives = [mock_alternative]
        
        mock_transcript.channel = mock_channel
        
        # Invocar el handler interno
        with caplog.at_level(logging.DEBUG):
            await provider._on_transcript_received(mock_transcript)
        
        # Verificar que el callback fue llamado con los argumentos correctos
        mock_callback.assert_called_once_with("Hola mundo", False)

    @pytest.mark.asyncio
    async def test_disconnect_closes_connection(
        self, valid_settings: Settings
    ) -> None:
        """AC 2: disconnect() cierra la conexión WebSocket gracefully."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        with patch(
            "src.infrastructure.providers.deepgram_asr_provider.AsyncDeepgramClient"
        ) as mock_client_class:
            mock_live_connection = AsyncMock()
            mock_live_connection.start_listening = AsyncMock()
            mock_live_connection.send_close_stream = AsyncMock()
            mock_live_connection.on = MagicMock(return_value=None)
            
            mock_connection_ctx = AsyncMock()
            mock_connection_ctx.__aenter__.return_value = mock_live_connection
            mock_connection_ctx.__aexit__ = AsyncMock()

            mock_client_instance = MagicMock()
            mock_client_instance.listen.v1.connect.return_value = mock_connection_ctx
            mock_client_class.return_value = mock_client_instance
            
            await provider.connect()
            assert provider._is_connected is True
            
            await provider.disconnect()
            
            mock_live_connection.send_close_stream.assert_called_once()
            assert provider._is_connected is False

    @pytest.mark.asyncio
    async def test_send_audio_without_connection_is_safe(
        self, valid_settings: Settings
    ) -> None:
        """AC 2: send_audio() es seguro si no hay conexión activa."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        # No llamar a connect(), el estado debe estar desconectado
        audio_chunk = b"\x00\x01\x02\x03"
        
        # No debe lanzar excepción, solo loguear warning
        await provider.send_audio(audio_chunk)
        
        assert provider._is_connected is False


class TestDeepgramASRProviderResilience:
    """Pruebas de resiliencia (AC 3: Máximo 3 reintentos)."""

    @pytest.fixture
    def valid_settings(self) -> Settings:
        """Settings con API Key válida."""
        return Settings(
            app_env="test",
            app_port=8000,
            base_url="http://localhost:8000",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            supabase_db_url="postgresql://test",
            supabase_jwt_secret="test-secret",
            deepgram_api_key="test-api-key-valid",
        )

    @pytest.mark.asyncio
    async def test_connect_retries_up_to_3_times_on_failure(
        self, valid_settings: Settings, caplog
    ) -> None:
        """AC 3: connect() reintenta hasta 3 veces ante fallos de conexión."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        with patch(
            "src.infrastructure.providers.deepgram_asr_provider.AsyncDeepgramClient"
        ) as mock_client_class:
            # Simular que los primeros 2 intentos fallan, el tercero tiene éxito
            mock_live_connection = AsyncMock()
            mock_live_connection.start_listening = AsyncMock()
            mock_live_connection.on = MagicMock(return_value=None)
            
            mock_connection_ctx = AsyncMock()
            mock_connection_ctx.__aenter__.side_effect = [
                ConnectionError("Network error"),  # Falla 1
                ConnectionError("Network error"),  # Falla 2
                mock_live_connection,  # Éxito en el 3er intento
            ]

            mock_client_instance = MagicMock()
            mock_client_instance.listen.v1.connect.return_value = mock_connection_ctx
            mock_client_class.return_value = mock_client_instance
            
            # Capturar logs para verificar reintentos
            with caplog.at_level(logging.WARNING):
                await provider.connect()
            
            # Verificar que se conectó después de los reintentos
            assert provider._is_connected is True
            # Verificar que __aenter__ fue llamado 3 veces
            assert mock_connection_ctx.__aenter__.call_count == 3

    @pytest.mark.asyncio
    async def test_connect_fails_after_3_retries(
        self, valid_settings: Settings
    ) -> None:
        """AC 3: connect() falla después de exactamente 3 intentos fallidos."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        with patch(
            "src.infrastructure.providers.deepgram_asr_provider.AsyncDeepgramClient"
        ) as mock_client_class:
            # Simular que todos los 3 intentos fallan
            mock_live_connection = AsyncMock()
            mock_live_connection.start_listening = AsyncMock()
            mock_live_connection.on = MagicMock(return_value=None)
            
            mock_connection_ctx = AsyncMock()
            mock_connection_ctx.__aenter__.side_effect = ConnectionError("Network error")

            mock_client_instance = MagicMock()
            mock_client_instance.listen.v1.connect.return_value = mock_connection_ctx
            mock_client_class.return_value = mock_client_instance
            
            # Debe lanzar excepción después de 3 reintentos
            with pytest.raises(ConnectionError):
                await provider.connect()
            
            # Verificar que se intentó exactamente 3 veces (no más)
            assert mock_connection_ctx.__aenter__.call_count == 3
            assert provider._is_connected is False

    @pytest.mark.asyncio
    async def test_connect_retries_on_deepgram_api_error(
        self, valid_settings: Settings
    ) -> None:
        """AC 3: connect() reintenta también en errores de API (429, 5xx)."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        with patch(
            "src.infrastructure.providers.deepgram_asr_provider.AsyncDeepgramClient"
        ) as mock_client_class:
            mock_live_connection = AsyncMock()
            mock_live_connection.start_listening = AsyncMock()
            mock_live_connection.on = MagicMock(return_value=None)
            
            mock_connection_ctx = AsyncMock()
            mock_connection_ctx.__aenter__.side_effect = [
                Exception("HTTP 429: Too Many Requests"),  # Rate limit
                Exception("HTTP 500: Internal Server Error"),  # 5xx
                mock_live_connection,  # Éxito
            ]

            mock_client_instance = MagicMock()
            mock_client_instance.listen.v1.connect.return_value = mock_connection_ctx
            mock_client_class.return_value = mock_client_instance
            
            # Debe conectarse después de los reintentos
            await provider.connect()
            
            assert provider._is_connected is True
            assert mock_connection_ctx.__aenter__.call_count == 3


class TestDeepgramASRProviderErrorHandling:
    """Pruebas de manejo de errores (robustez general)."""

    @pytest.fixture
    def valid_settings(self) -> Settings:
        """Settings con API Key válida."""
        return Settings(
            app_env="test",
            app_port=8000,
            base_url="http://localhost:8000",
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
            supabase_db_url="postgresql://test",
            supabase_jwt_secret="test-secret",
            deepgram_api_key="test-api-key-valid",
        )

    @pytest.mark.asyncio
    async def test_connection_error_handler_logs_and_disconnects(
        self, valid_settings: Settings, caplog
    ) -> None:
        """El handler de errores de conexión registra y marca como desconectado."""
        provider = DeepgramASRProvider(settings=valid_settings)
        provider._is_connected = True
        
        mock_error = Exception("WebSocket closed unexpectedly")
        
        with caplog.at_level(logging.ERROR):
            await provider._on_connection_error(mock_error)
        
        assert provider._is_connected is False
        assert "Error de conexión Deepgram" in caplog.text

    @pytest.mark.asyncio
    async def test_transcript_handler_gracefully_handles_missing_data(
        self, valid_settings: Settings
    ) -> None:
        """El handler de transcripción maneja datos incompletos gracefully."""
        provider = DeepgramASRProvider(settings=valid_settings)
        
        mock_callback = AsyncMock()
        await provider.set_transcript_handler(mock_callback)
        
        # Simular un objeto TranscriptResponse incompleto (sin canal)
        mock_transcript = MagicMock()
        mock_transcript.channel = None
        
        # No debe lanzar excepción
        await provider._on_transcript_received(mock_transcript)
        
        # El callback no debe ser llamado si no hay resultados
        mock_callback.assert_not_called()
