"""Validator for Twilio webhook signatures — OWASP security."""

import logging
from twilio.request_validator import RequestValidator

logger = logging.getLogger(__name__)


class TwilioWebhookValidator:
    """
    Valida la firma de webhooks de Twilio para asegurar autenticidad de origen.
    
    Implementa la validación recomendada por Twilio usando el SDK oficial:
    https://www.twilio.com/docs/usage/webhooks/webhooks-security
    """

    def __init__(self, auth_token: str) -> None:
        """Inicializa el validador.
        
        Args:
            auth_token: Twilio Auth Token de la cuenta
        """
        self.validator = RequestValidator(auth_token)

    def validate_signature(
        self, url: str, data: dict, signature_header: str
    ) -> bool:
        """Valida que la firma es genuina de Twilio.
        
        Args:
            url: URL completa del webhook que Twilio llamó
            data: Dict con los parámetros POST
            signature_header: Valor del header X-Twilio-Signature
            
        Returns:
            True si la firma es válida, False si no
        """
        # El validador oficial del SDK requiere que el dict no tenga arrays encadenados,
        # lo cual FastAPI (Starlette) usualmente parsea como values singulares para
        # llamadas simples, que es compatible directamente.
        is_valid = self.validator.validate(url, data, signature_header)
        
        if not is_valid:
            logger.warning(f"Invalid Twilio signature for url: {url}")
            
        return is_valid
