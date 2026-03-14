"""Validator for Twilio webhook signatures — OWASP security."""

import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


class TwilioWebhookValidator:
    """
    Valida la firma de webhooks de Twilio para asegurar autenticidad de origen.
    
    Implementa la validación recomendada por Twilio:
    https://www.twilio.com/docs/usage/webhooks/webhooks-security
    """

    def __init__(self, auth_token: str) -> None:
        """Inicializa el validador.
        
        Args:
            auth_token: Twilio Auth Token de la cuenta
        """
        self.auth_token = auth_token

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
        try:
            # Reconstruir el string que Twilio firmó
            # Orden importa: URL + parámetros sorted
            s = url
            for key in sorted(data.keys()):
                s += key + str(data[key])
            
            # Generar la firma esperada usando HMAC-SHA1
            mac = hmac.new(
                self.auth_token.encode(),
                s.encode(),
                hashlib.sha1
            )
            expected_signature = mac.digest()
            
            # Decodificar la firma recibida de base64
            import base64
            try:
                received_signature = base64.b64decode(signature_header)
            except Exception:
                logger.warning("Could not decode X-Twilio-Signature header")
                return False
            
            # Comparar con constant-time comparison
            is_valid = hmac.compare_digest(expected_signature, received_signature)
            
            if not is_valid:
                logger.warning(
                    f"Invalid Twilio signature: expected "
                    f"{base64.b64encode(expected_signature)}, "
                    f"got {signature_header}"
                )
            
            return is_valid
        except Exception as e:
            logger.error(f"Error validating Twilio signature: {e}")
            return False
