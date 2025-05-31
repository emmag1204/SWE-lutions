import asyncio
import os
import requests
import base64
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent


def get_github_issue(repo_owner: str, repo_name: str, issue_number: int, token: str = "") -> str:
    """Fetch GitHub issue details using GitHub API"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue_number}"
    headers = {"Authorization": f"token {token}"} if token else {}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        issue_data = response.json()
        
        return f"""
        Title: {issue_data['title']}
        State: {issue_data['state']}
        URL: {issue_data['html_url']}
        Body: {issue_data['body']}
        """
    except Exception as e:
        return f"Error fetching issue: {str(e)}"

def get_repository_structure(repo_owner: str, repo_name: str, path: str = "", token: str = "") -> str:
    """Fetch repository file structure"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}"
    headers = {"Authorization": f"token {token}"} if token else {}
    
    try:
        response = requests.get(url, headers=headers)
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
        return f"Error fetching repository structure: {str(e)}"

def get_file_content(repo_owner: str, repo_name: str, file_path: str, token: str = "") -> str:
    """Fetch specific file content from repository"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
    headers = {"Authorization": f"token {token}"} if token else {}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        file_data = response.json()
        
        if file_data.get('encoding') == 'base64':
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return f"Content of {file_path}:\n{content}"
        else:
            return f"Could not decode file content for {file_path}"
    except Exception as e:
        return f"Error fetching file {file_path}: {str(e)}"

# def search_python_files(repo_owner: str, repo_name: str, token: str = "") -> str:
#     try:
#         structure = get_repository_structure(repo_owner, repo_name, "", token)
        
#         python_files = []
#         for line in structure.split('\n'):
#             if line.startswith('FILE:') and line.endswith('.py'):
#                 file_path = line.replace('FILE: ', '')
#                 python_files.append(file_path)
        
#         file_contents = []
#         for file_path in python_files[:5]: 
#             content = get_file_content(repo_owner, repo_name, file_path, token)
#             file_contents.append(content)
        
#         return f"Python files found:\n{chr(10).join(python_files)}\n\n" + "\n\n".join(file_contents)
#     except Exception as e:
#         return f"Error searching Python files: {str(e)}"

async def main():
    # Missing temperature and top_p settings
    config = { 
        "api_type": "azure",
        "api_key": os.getenv("AGENTS_API_KEY"),
        "base_url": os.getenv("AGENTS_API_BASE_URL"),
        "api_version": os.getenv("AGENTS_API_VERSION"),
        "model": os.getenv("AGENTS_MODEL_NAME", "gpt-4o")
    }

    
    analyzer = AssistantAgent(
        name="analyzer", 
        llm_config={"config_list": [config]}, 
        system_message="""You are a GitHub issue analyzer. Your job is to:

            1. Fetch GitHub issue details using get_github_issue function
            2. Get repository structure using get_repository_structure function  
            3. Search for Python files using search_python_files function
            4. Get specific file content using get_file_content function
            5. Analyze the issue and identify the problematic file path
            6. Create a JSON analysis with ALL required fields filled

            IMPORTANT RULES:
            - ALWAYS say "This might be the filepath of the issue: [filepath]" when you identify a potential problematic file
            - ALWAYS fetch as much repository code as possible to understand the context
            - ALWAYS return a complete JSON file to the SWE agent with these exact fields:
            {
                "problem_statement": "Clear description of the issue",
                "filepath": "Path to the problematic file", 
                "first_guess": "Your hypothesis about what's wrong",
                "paradigm": "The programming paradigm used, possible return valeus must be 'Procedural Programming',
                'Objected-Oriented Programming', 'Procedural and Objected-Oriented Programming', 'Simple Text',
            }
            - ALWAYS print the JSON on the terminal
            - NEVER pass incomplete JSON to SWE-Agent - iterate until all fields are filled
            - If you need more information, fetch more files or ask for clarification
            - PLEASE make sure to always provide all the information needed for the SWE-agent to create a patch don't 
            stop iterating until you have all the information for the SWE-Agent, always print the JSON on the terminal and pass info to SWE-Agent"""
    )
    
    analyzer.register_for_execution(name="get_github_issue")(get_github_issue)
    analyzer.register_for_llm(description="Fetch GitHub issue details by repo owner, repo name, and issue number")(get_github_issue)
    analyzer.register_for_execution(name="get_repository_structure")(get_repository_structure)
    analyzer.register_for_llm(description="Get repository file and folder structure")(get_repository_structure)
    analyzer.register_for_execution(name="get_file_content")(get_file_content)
    analyzer.register_for_llm(description="Get content of a specific file from repository")(get_file_content)
    # analyzer.register_for_execution(name="search_python_files")(search_python_files)
    # analyzer.register_for_llm(description="Search for and get content of Python files in repository")(search_python_files)
    
    swe_agent = AssistantAgent(
        name="swe_agent", 
        llm_config={"config_list": [config]}, 
        system_message="""You're a software engineer. When you receive a JSON analysis from the analyzer:

                1. Read the problem_statement, filepath, first_guess, and paradigm
                2. Create a code fix/patch for the issue
                3. Format your response as a proper patch in diff format
                4. ALWAYS print the patch in this exact format:

                **Patch**:
                ```diff
                --- a/[filename]
                +++ b/[filename]  
                @@ -[old_line_start],[old_line_count] +[new_line_start],[new_line_count] @@
                -[removed lines with - prefix]
                +[added lines with + prefix]
                ```

                5. Return a JSON response with:
                {
                "patch": "The diff patch content",
                "filepath": "Path to the file being patched", 
                "solution_description": "Explanation of what the patch does"
                }

                IMPORTANT: Always print the patch and JSON visually on terminal"""
    )
    
    reviser = AssistantAgent(
        name="reviser",
        llm_config={"config_list": [config]}, 
        system_message="You review patches and determine if they solve the problem. Respond with 'LGTM 👍' if approved, otherwise provide go back to" \
        "SWE-Agent to create a new proper patch that will fix the error and check again if the patch is correct. Answer with 'LGTM 👍'" \
    )
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
    manager = GroupChatManager(groupchat=groupchat, llm_config={"config_list": [config]})
    user.initiate_chat(
        manager, 
        message="Analyzer, please fetch and analyze GitHub issue #1 from SWE-Agent/test-repo repository. Get the repository structure, find relevant files, and provide a complete JSON analysis."
    )

if __name__ == "__main__":
    asyncio.run(main())