import asyncio
import os
import json
import yaml
import re
from dotenv import load_dotenv
import requests
import base64
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent

# Carga YAML sin modificar estructura
def load_agent_from_yaml(filepath, config):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {filepath}")
        print(f"Asegúrate que el archivo exista en el directorio actual.")
        raise

    return AssistantAgent(
        name=data["name"],
        system_message=data["system_message"],
        llm_config={"config_list": [config], "temperature": data.get("temperature", 0.1)}
    )

def convert_web_url_to_api(url: str) -> str:
    try:
        if "github.com" in url and "/issues/" in url:
            parts = url.split("github.com/")[1].split("/issues/")
            repo_path = parts[0]
            issue_number = parts[1]
            return f"https://api.github.com/repos/{repo_path}/issues/{issue_number}"
        else:
            raise ValueError("Formato de URL no reconocido")
    except Exception as e:
        return f"Error convirtiendo URL: {str(e)}"

def get_github_issue(issue_url: str) -> str:
    try:
        response = requests.get(issue_url)
        response.raise_for_status()
        issue_data = response.json()

        return f"""
Title: {issue_data['title']}
State: {issue_data['state']}
URL: {issue_data['html_url']}
Body: {issue_data['body']}
"""
    except Exception as e:
        return f"Error obteniendo issue: {str(e)}"

def get_repository_structure(repo_owner: str, repo_name: str, path: str = "") -> str:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        contents = response.json()

        structure = []
        for item in contents:
            if item['type'] == 'file':
                structure.append(f"FILE: {item['path']}")
            elif item['type'] == 'dir':
                structure.append(f"DIR: {item['path']}/")
        return "\n".join(structure)
    except Exception as e:
        return f"Error obteniendo estructura del repo: {str(e)}"

def get_file_content(repo_owner: str, repo_name: str, file_path: str) -> str:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        file_data = response.json()

        if file_data.get('encoding') == 'base64':
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return f"Contenido de {file_path}:\n{content}"
        else:
            return f"No se pudo decodificar el contenido de {file_path}"
    except Exception as e:
        return f"Error obteniendo archivo {file_path}: {str(e)}"

class AnalyzerDataStore:
    def _init_(self):
        self.json_data = None
        self.raw_content = None
        self.timestamp = None

    def save_data(self, json_data, raw_content=None):
        self.json_data = json_data
        self.raw_content = raw_content
        self.timestamp = asyncio.get_event_loop().time()

    def get_data(self):
        return {
            'json_data': self.json_data,
            'raw_content': self.raw_content,
            'timestamp': self.timestamp
        }

    def has_data(self):
        return self.json_data is not None

analyzer_store = AnalyzerDataStore()

class CustomGroupChatManager(GroupChatManager):
    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)
        self.analyzer_json = None
        self.swe_json = None

    def _process_received_message(self, message, sender, silent):
        result = super()._process_received_message(message, sender, silent)

        if hasattr(sender, 'name'):
            content = ""
            if isinstance(message, dict):
                content = message.get('content', '') or str(message)
            elif isinstance(message, str):
                content = message
            else:
                content = str(message)

            if sender.name == "analyzer":
                match = re.search(r"\{[\s\S]*?\}", content)
                if match:
                    try:
                        analyzer_json = json.loads(match.group())
                        self.analyzer_json = analyzer_json
                        with open("analyzer_output.json", "w") as f:
                            json.dump(analyzer_json, f, indent=2)
                    except Exception as e:
                        print(f"Error parsing analyzer JSON: {e}")

            elif sender.name == "swe_agent":
                match = re.search(r"\{[\s\S]*?\}", content)
                if match:
                    try:
                        swe_json = json.loads(match.group())
                        self.swe_json = swe_json
                        with open("swe_agent_output.json", "w") as f:
                            json.dump(swe_json, f, indent=2)
                        reviser_agent = None
                        for agent in self.groupchat.agents:
                            if agent.name == "reviser":
                                reviser_agent = agent
                                break
                        if reviser_agent:
                            swe_message = json.dumps(swe_json, indent=2)
                            self.groupchat.send_message(
                                sender=self.groupchat.get_agent_by_name("swe_agent"),
                                recipient=reviser_agent,
                                message=swe_message
                            )
                            print("✅ Enviado output de SWE Agent al reviser.")
                        else:
                            print("❌ No se encontró agente reviser en el groupchat.")
                    except Exception as e:
                        print(f"Error parsing SWE JSON: {e}")
        return result

    def get_analyzer_data(self):
        return self.analyzer_json

    def get_swe_data(self):
        return self.swe_json

async def main():
    load_dotenv()

    user_input_url = input("Introduce la URL del issue de GitHub: ").strip()
    issue_url = convert_web_url_to_api(user_input_url)

    # Configuraciones LLM separadas
    config_analyzer = {
        "api_type": "azure",  # o "local" si usas local
        "api_key": os.getenv("AGENTS_API_KEY"),
        "base_url": os.getenv("AGENTS_API_BASE_URL"),
        "api_version": os.getenv("AGENTS_API_VERSION"),
        "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
    }

    config_swe_agent = {
        "api_type": "qwen",
        "api_key": os.getenv("QWEN_API_KEY"),
        "base_url": os.getenv("QWEN_API_BASE_URL", "http://localhost:7000"),
        "model": "qwen-7b"
    }

    config_reviser = {
        "api_type": "azure",
        "api_key": os.getenv("AGENTS_API_KEY"),
        "base_url": os.getenv("AGENTS_API_BASE_URL"),
        "api_version": os.getenv("AGENTS_API_VERSION"),
        "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
    }

    # Verificar archivos YAML
    yaml_files = ["analyzer.yaml", "swe_agent.yaml", "reviser.yaml"]
    for yaml_file in yaml_files:
        if not os.path.exists(yaml_file):
            print(f"Error: No se encontró el archivo {yaml_file}")
            print(f"Archivos en el directorio actual: {os.listdir('.')}")
            return

    # Cargar agentes con sus configs respectivas
    analyzer = load_agent_from_yaml("analyzer.yaml", config_analyzer)
    swe_agent = load_agent_from_yaml("swe_agent.yaml", config_swe_agent)
    reviser = load_agent_from_yaml("reviser.yaml", config_reviser)
    print("✅ Agentes cargados exitosamente desde YAML")

    # Registrar funciones para analyzer
    analyzer.register_for_execution(name="get_github_issue")(get_github_issue)
    analyzer.register_for_llm(description="Fetch GitHub issue details using the full issue API URL")(get_github_issue)
    analyzer.register_for_execution(name="get_repository_structure")(get_repository_structure)
    analyzer.register_for_llm(description="Get repository file and folder structure")(get_repository_structure)
    analyzer.register_for_execution(name="get_file_content")(get_file_content)
    analyzer.register_for_llm(description="Get content of a specific file from repository")(get_file_content)

    # Crear agente usuario (sin input humano en este ejemplo)
    user = UserProxyAgent(
        name="user",
        code_execution_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: "LGTM" in x.get("content", "") or "👍" in x.get("content", "")
    )

    # Crear grupo de chat con todos los agentes
    groupchat = GroupChat(
        agents=[user, analyzer, swe_agent, reviser],
        messages=[],
        max_round=20
    )

    # Crear manager personalizado
    manager = CustomGroupChatManager(
        groupchat=groupchat,
        llm_config={"config_list": [config_analyzer], "temperature": 0.1}
    )

    # Registrar el listener del manager para controlar flujos
    # Enviaremos mensajes manualmente para forzar el flujo secuencial:
    # 1) usuario -> analyzer
    # 2) analyzer -> swe_agent
    # 3) swe_agent -> reviser

    # Enviar el input inicial al analyzer
    manager.groupchat.send_message(
        sender=user,
        recipient=analyzer,
        message=f"Por favor analiza este issue:\n{issue_url}"
    )

    # Ejecutar el loop del manager
    await manager.run_chat()

if __name__ == "__main__":
    asyncio.run(main())