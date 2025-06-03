from autogen import AssistantAgent
import yaml

def load_agent_from_yaml(filepath, config):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = yaml.safe_load(f)
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as f:
                data = yaml.safe_load(f)

    return AssistantAgent(
        name=data["name"],
        system_message=data["system_message"],
        llm_config={"config_list": [config], "temperature": data.get("temperature", 0.1)}
    )
