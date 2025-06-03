import requests
import base64

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
        return f"Error fetching issue: {str(e)}"

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
        return f"Error fetching repository structure: {str(e)}"

def get_file_content(repo_owner: str, repo_name: str, file_path: str) -> str:
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        file_data = response.json()

        if file_data.get('encoding') == 'base64':
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return f"Content of {file_path}:\n{content}"
        else:
            return f"Could not decode file content for {file_path}"
    except Exception as e:
        return f"Error fetching file {file_path}: {str(e)}"
