import os
import re
import json
from tabulate import tabulate
import asyncio
from dotenv import load_dotenv
from autogen import GroupChat, GroupChatManager, UserProxyAgent
from analyzer import load_agent_from_yaml, get_github_issue, get_repository_structure, get_file_content
from swe_agent import load_agent_from_yaml as load_swe_agent
from reviser import load_agent_from_yaml as load_reviser_agent

def convert_web_url_to_api(url: str) -> str:
    try:
        if "github.com" in url and "/issues/" in url:
            parts = url.split("github.com/")[1].split("/issues/")
            repo_path = parts[0]
            issue_number = parts[1]
            return f"https://api.github.com/repos/{repo_path}/issues/{issue_number}"
        else:
            raise ValueError("URL format not recognized")
    except Exception as e:
        return f"Error converting URL: {str(e)}"

class CustomGroupChatManager(GroupChatManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
                            print("Sent SWE JSON output to reviser.")
                        else:
                            print("Reviser agent not found in groupchat.")

                    except Exception as e:
                        print(f"Error parsing SWE JSON: {e}")
        return result

async def main():
    load_dotenv()
    user_input_url = input("Enter GitHub issue url: ").strip()
    issue_url = convert_web_url_to_api(user_input_url)

    config = {
        "api_type": "azure",
        "api_key": os.getenv("AGENTS_API_KEY"),
        "base_url": os.getenv("AGENTS_API_BASE_URL"),
        "api_version": os.getenv("AGENTS_API_VERSION"),
        "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
    }

    yaml_files = ["analyzer.yaml", "swe_agent.yaml", "reviser.yaml"]
    for yaml_file in yaml_files:
        if not os.path.exists(yaml_file):
            print(f"Error: No se encontró el archivo {yaml_file}")
            print(f"Archivos en el directorio actual: {os.listdir('.')}")
            return

    analyzer = load_agent_from_yaml("analyzer.yaml", config)
    swe_agent = load_swe_agent("swe_agent.yaml", config)
    reviser = load_reviser_agent("reviser.yaml", config)
    print("✅ Agentes cargados exitosamente desde archivos YAML")

    analyzer.register_for_execution(name="get_github_issue")(get_github_issue)
    analyzer.register_for_llm(description="Fetch GitHub issue details using the full issue API URL")(get_github_issue)
    analyzer.register_for_execution(name="get_repository_structure")(get_repository_structure)
    analyzer.register_for_llm(description="Get repository file and folder structure")(get_repository_structure)
    analyzer.register_for_execution(name="get_file_content")(get_file_content)
    analyzer.register_for_llm(description="Get content of a specific file from repository")(get_file_content)

    user = UserProxyAgent(
        name="user",
        code_execution_config=False,
        human_input_mode="NEVER",
        is_termination_msg=lambda x: "LGTM" in x.get("content", "") or "👍" in x.get("content", "")
    )

    groupchat = GroupChat(
        agents=[user, analyzer, swe_agent, reviser],
        messages=[],
        max_round=20
    )

    manager = CustomGroupChatManager(
        groupchat=groupchat,
        llm_config={"config_list": [config], "temperature": 0.5}
    )

    user.initiate_chat(
        manager,
        message=f"Analyzer, please fetch and analyze the issue from {issue_url}"
    )

if __name__ == "__main__":
    asyncio.run(main())
