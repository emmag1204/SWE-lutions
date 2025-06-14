import os
import subprocess
import sys
import json
from openai import AzureOpenAI
import requests
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

# Azure OpenAI config
load_dotenv()
CLIENT = AzureOpenAI(
    azure_endpoint=os.getenv("AGENTS_API_BASE_URL"),
    api_key=os.getenv("AGENTS_API_KEY"),
    api_version=os.getenv("AGENTS_API_VERSION")
)

def transform_github_url_to_api(issue_url):
    parsed = urlparse(issue_url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 4 or parts[-2] != "issues":
        raise ValueError("Invalid GitHub issue URL")
    owner, repo, _, issue_number = parts
    return f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}", owner, repo

def fetch_issue_data(api_url):
    headers = {"Accept": "application/vnd.github+json"}
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_repo_tree(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    response = requests.get(url)
    response.raise_for_status()
    tree_data = response.json().get("tree", [])
    return [item['path'] for item in tree_data if item['type'] == 'blob']

def fetch_file_content(owner, repo, filepath):
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{filepath}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    return ""

def build_codebase(owner, repo, paths):
    codebase = {}
    for path in paths:
        code = fetch_file_content(owner, repo, path)
        codebase[path] = code
    return codebase
def guess_most_relevant_file(problem_statement, tree_data):
    prompt = f"""
You are an assistant helping a software engineer fix an issue.

Given this problem statement:
---
{problem_statement}
---

And here is the code tree data:
---
{tree_data}
---
Which file is most likely to be the one that contains the bug? Return only the file path, try to always return a file path, even if you are not sure.
Response example: `path/to/file.py`
        """
    try:
        response = CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Exception: GPT-4 guess failed: {e}")
        return None


def guess_what_went_wrong(problem_statement, file_guess):
    prompt = f"""
Given this problem statement:
---
{problem_statement}
---

And the most relevant file: {file_guess}

What is likely the root cause of this issue? Provide a brief, direct analysis in 1-2 sentences, try to always return something on this field.
"""
    
    try:
        response = CLIENT.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Exception: Failed to guess what went wrong: {e}")
        return "Unable to analyze the problem at this time."



def run_analyzer(issue_url):
    api_url, owner, repo = transform_github_url_to_api(issue_url)
    issue_data = fetch_issue_data(api_url)
    title = issue_data.get("title", "")
    body = issue_data.get("body", "")
    problem_statement = f"{title}\n\n{body}"

    file_paths = fetch_repo_tree(owner, repo)
    # codebase = build_codebase(owner, repo, file_paths)

    file_guess = guess_most_relevant_file(problem_statement, file_paths)

    first_guess = guess_what_went_wrong(problem_statement, file_guess)

    analyzer_result = {
        "problem_statement": problem_statement,
        "github_url": issue_url,
        "first_guess": first_guess,
        "filepath": file_guess  # optional: truncate or remove if too large
    }

    return analyzer_result


# SWE-Agent
def truncate_github_url(issue_url):
    """Truncate the GitHub issue URL to return the repository URL.
    Format issue_url: https://github.com/<owner>/<repo>/issues/<issue_number>"""
    parsed = urlparse(issue_url)
    parts = parsed.path.strip("/").split("/")
    #  Return https://github.com/<owner>/<repo>
    if len(parts) < 3:
        raise ValueError("Invalid GitHub issue URL")
    owner, repo = parts[0], parts[1]
    return f"https://github.com/{owner}/{repo}"


def send_to_swe_agent(data):
    # Mocked call to SWE agent - replace with actual implementation
    github_repo_url = truncate_github_url(data['github_url'])
    problem_statement_github_url = data['github_url']

    # Run python SWE-Agent/sweagent/run/run.py run \
    # --env.repo.github_url={github_repo_url} \
    # --problem.statement.github_url={problem_statement_github_url} \
    # --config SWE-Agent/config/custom_env.yaml 
    result = subprocess.run([
        "python", "SWE-agent/sweagent/run/run.py", "run",
        "--config", "SWE-agent/config/custom_env.yaml",
        f"--env.repo.github_url={github_repo_url}",
        f"--problem_statement.github_url={problem_statement_github_url}"
    ], capture_output=True, text=True)
    print("\n -------------------------------------------------------\n")
    print(result.stdout)
    print("\n------------------------------------------------------\n\n")

    # Need to find the result of PATCH_FILE_PATH from result.stdout
    # Ex. PATCH_FILE_PATH='/home/omarmacma/Tec/AplicacionesAvanzadas/SWE-lutions/trajectories/omarmacma/custom_env__azure/gpt-4o__t-0.00__p-1.00__c-15.00___SWE-agent__test-repo-i1/SWE-agent__test-repo-i1/SWE-agent__te-repo-i1.patch'
    if "PATCH_FILE_PATH=" in result.stdout:
        patch_file_path = result.stdout.split("PATCH_FILE_PATH='")[1].split("'")[0]
        # Replace " \n " with "st"
        patch_file_path = patch_file_path.replace(" \n ", "st")
        patch_file_path = patch_file_path.strip()
    else:
        print("********************************************ERROR: PATCH_FILE_PATH not found in output.*********************************************")
        return
    print(f"📂 Patch file generated at: {patch_file_path}")
    with open(patch_file_path, 'r') as file:
        patch_content = file.read()
    data['patch'] = patch_content
    print("\n📜 Patch content:")
    print(patch_content[:500] + "\n...\n" if len(patch_content) > 500 else patch_content)
    return patch_content


# Revisor
class Revisor:
    def __init__(self):
        """Initialize the code reviewer with Azure OpenAI configuration"""
        self.system_prompt = """You are a lenient code reviewer. Your task is to analyze patches and determine if they should be approved or need fixes.

You will receive:
1. A problem statement describing what needs to be solved
2. A code patch that attempts to solve the problem

Your evaluation criteria (be LENIENT):
- Does the patch solve the core problem? (Minor issues are okay)
- Are there any critical bugs that would break functionality?
- IGNORE: Variable name changes, refactoring, style preferences, minor optimizations
- IGNORE: Code formatting, spacing, naming conventions
- IGNORE: Performance optimizations unless critical
- ONLY flag as NEEDS_FIX if there are serious functional issues

Be generous with approvals. Focus only on whether the patch fundamentally works and solves the problem.
Minor improvements, refactoring, and style changes should NOT prevent approval.

You must respond with a JSON object containing:
{
    "status": "APPROVED" or "NEEDS_FIX",
    "confidence": 0.0-1.0,
    "reason": "Brief explanation of your decision",
    "issues_found": ["list", "of", "critical", "issues", "only"],
    "suggestions": ["list", "of", "optional", "improvements"]
}

Default to APPROVED unless there are serious functional problems.
Return no more than 2 suggestions and 2 issues at most."""

    def _call_gpt(self, messages):
        """Make API call to Azure OpenAI using the client"""
        try:
            response = CLIENT.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            return response.choices[0].message.content

        except Exception as e:
            return f"API Error: {str(e)}"

    def review_patch(self, problem_statement: str, patch: str) -> dict:
        """Review a code patch against a problem statement"""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"""Please review this code patch:

PROBLEM STATEMENT:
{problem_statement}

CODE PATCH:
{patch}

Provide your analysis as a JSON object with the required fields."""}
            ]

            response = self._call_gpt(messages)
            review_result = self._extract_json_from_response(response)

            if review_result:
                return review_result
            else:
                return {
                    "status": "ERROR",
                    "confidence": 0.0,
                    "reason": "Failed to parse reviewer response",
                    "issues_found": ["Response parsing error"],
                    "suggestions": ["Retry the review"]
                }

        except Exception as e:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "reason": f"Review process failed: {str(e)}",
                "issues_found": [f"System error: {str(e)}"],
                "suggestions": ["Check system configuration and retry"]
            }

    def _extract_json_from_response(self, response: str) -> dict:
        """Extract JSON object from GPT response"""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                result = json.loads(json_str)

                if isinstance(result.get("suggestions"), list):
                    result["suggestions"] = result["suggestions"][:2]
                if isinstance(result.get("issues_found"), list):
                    result["issues_found"] = result["issues_found"][:2]

                return result
            else:
                if "APPROVED" in response.upper():
                    status = "APPROVED"
                elif "NEEDS_FIX" in response.upper() or "FIX" in response.upper():
                    status = "NEEDS_FIX"
                else:
                    status = "UNCLEAR"

                return {
                    "status": status,
                    "confidence": 0.5,
                    "reason": response[:200] + "..." if len(response) > 200 else response,
                    "issues_found": [],
                    "suggestions": []
                }

        except json.JSONDecodeError:
            return None

    def review_from_json(self, input_json: str) -> dict:
        """Review patch from JSON input"""
        try:
            data = json.loads(input_json)
            problem_statement = data.get('problem_statement', '')
            patch = data.get('patch', '')

            if not problem_statement or not patch:
                return {
                    "status": "ERROR",
                    "confidence": 0.0,
                    "reason": "Missing required fields: problem_statement and/or patch",
                    "issues_found": ["Invalid input format"],
                    "suggestions": ["Provide both problem_statement and patch fields"]
                }

            return self.review_patch(problem_statement, patch)

        except json.JSONDecodeError as e:
            return {
                "status": "ERROR",
                "confidence": 0.0,
                "reason": f"Invalid JSON input: {str(e)}",
                "issues_found": ["JSON parsing error"],
                "suggestions": ["Check JSON format and try again"]
            }


def run_revisor(swe_agent_output_dict: str) -> dict:
    reviewer = Revisor()

    result = reviewer.review_patch(
        problem_statement=swe_agent_output_dict.get("problem_statement", ""),
        patch=swe_agent_output_dict.get("patch", "")
    )
    return result



def main():
    if len(sys.argv) < 2:
        print("Usage: python3 multiagents.py <GitHub Issue URL>")
        sys.exit(1)

    issue_url = sys.argv[1]
    print(f"Processing GitHub issue URL: {issue_url}")
    analyzer_result = run_analyzer(issue_url)
    print("\n------------------------------------------------------\nAnalyzer Result:")
    print(json.dumps(analyzer_result, indent=2))
    print("\n------------------------------------------------------\n")

    print("Initiating SWE-Agent to generate a patch...")

    patch = send_to_swe_agent(analyzer_result)
    if patch and analyzer_result["problem_statement"]:
        swe_output_json = {
            "problem_statement": analyzer_result["problem_statement"],
            "patch": patch,
        }

        print("\n------------------------------------------------------\nRevision Outcome:")
        print(run_revisor(swe_output_json))
    else:
        print("No patch generated or problem statement missing. Exiting.")


if __name__ == "__main__":
    load_dotenv()
    main()