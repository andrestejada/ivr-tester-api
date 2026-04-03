import asyncio
import os
import httpx
from dotenv import load_dotenv

from src.infrastructure.config import Settings
from src.infrastructure.providers.deepgram_asr_provider import DeepgramASRProvider

load_dotenv()

async def on_transcript(text: str, is_final: bool):
    print(f"[{'FINAL' if is_final else 'PARCIAL'}] {text}")

async def main():
    print("Iniciando prueba aislada del DeepgramASRProvider...")
    
    settings = Settings()
    provider = DeepgramASRProvider(settings=settings)
    
    await provider.set_transcript_handler(on_transcript)
    
    print("Conectando al WebSocket de Deepgram...")
    await provider.connect()
    
    AUDIO_FILE = "test-audio.wav"
    print(f"Transmitiendo audio desde archivo local: {AUDIO_FILE}")
    
    try:
        # Leer el archivo local en chunks
        with open(AUDIO_FILE, "rb") as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                
                await provider.send_audio(chunk)
                await asyncio.sleep(0.01)  # Simular streaming en tiempo real
        
        print("Lectura de archivo terminada. Esperando transcripciones finales...")
        await asyncio.sleep(3)
                    
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("Interrumpido por el usuario")
    except Exception as e:
        print(f"ERROR DURANTE STREAMING: {e}")
    finally:
        print("Cerrando conexión...")
        await provider.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
