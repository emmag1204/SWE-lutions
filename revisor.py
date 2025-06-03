import json
from autogen import AssistantAgent

class ReviserAgent(AssistantAgent):
    def _init_(self, name, system_message, llm_config):
        super()._init_(name=name, system_message=system_message, llm_config=llm_config)
        self.latest_swe_json = None

    def process_swe_response(self, swe_response: str):
        
        try:
            swe_json = json.loads(swe_response)
            self.latest_swe_json = swe_json
            # Aquí puedes agregar lógica adicional con swe_json
            # por ejemplo validar campos, generar reportes, etc.
            return True
        except json.JSONDecodeError as e:
            print(f"[{self.name}] Error parseando JSON de swe_agent: {e}")
            return False

    def on_message_received(self, message: str, sender_name: str):
     
        if sender_name != "swe_agent":
            return  # Ignorar mensajes que no sean de swe_agent

        success = self.process_swe_response(message)
        if not success:
            print(f"[{self.name}] Mensaje recibido inválido de swe_agent.")