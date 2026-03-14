"""Port (interface) for Call Provider — agnóstic de proveedor de telefonía."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CallSession:
    """Sesión de llamada activa con identificador único asignado por proveedor."""

    call_sid: str


class ICallProvider(ABC):
    """Interfaz agnóstica para proveedores de telefonía (Twilio, Vonage, etc.).
    
    Define los métodos necesarios para orquestar una llamada telefónica:
    - Iniciar una llamada
    - Enviar dígitos DTMF durante la llamada
    - Colgar la llamada
    
    La implementación concreta es responsable de traducir estas acciones
    al protocolo específico del proveedor (TwiML, etc.)
    """

    @abstractmethod
    async def initiate_call(
        self, phone_number: str, webhook_url: str
    ) -> CallSession:
        """Inicia una llamada telefónica.
        
        Args:
            phone_number: Número a marcar (ej: "+1234567890")
            webhook_url: URL del webhook que el proveedor llamará con instrucciones
            
        Returns:
            CallSession con call_sid asignado por el proveedor
            
        Raises:
            Exception si hay error (número inválido, línea ocupada, etc.)
        """
        pass

    @abstractmethod
    async def send_dtmf(self, call_sid: str, digits: str) -> None:
        """Envía dígitos DTMF a una llamada en curso.
        
        Args:
            call_sid: ID de la llamada (asignado por proveedor)
            digits: Dígitos a enviar (ej: "1", "2", "123")
            
        Raises:
            Exception si la llamada no existe o ya terminó
        """
        pass

    @abstractmethod
    async def hangup(self, call_sid: str) -> None:
        """Cuelga una llamada en curso.
        
        Args:
            call_sid: ID de la llamada a terminar
            
        Raises:
            Exception si la llamada no existe
        """
        pass
