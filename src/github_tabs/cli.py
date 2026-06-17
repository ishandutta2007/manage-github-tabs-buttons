import os
import sys
import argparse
import subprocess
import requests
import base64
from dotenv import load_dotenv

def get_git_remote_info():
    """Attempts to get owner and repo name from git remote origin."""
    try:
        # Get the remote URL
        url = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], 
                                    stderr=subprocess.STDOUT, 
                                    shell=True).decode().strip()
        
        # Strip .git suffix
        if url.endswith('.git'):
            url = url[:-4]
        
        # Handle SSH (git@github.com:owner/repo)
        if 'git@github.com:' in url:
            parts = url.split('git@github.com:')[-1].split('/')
            if len(parts) >= 2:
                return parts[0], parts[1]
        
        # Handle HTTPS (https://github.com/owner/repo)
        if 'https://github.com/' in url:
            parts = url.split('https://github.com/')[-1].split('/')
            if len(parts) >= 2:
                return parts[0], parts[1]
                
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None, None

def get_authenticated_user(token):
    """Fetches the username associated with the provided token."""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json'
    }
    try:
        response = requests.get('https://api.github.com/user', headers=headers)
        if response.status_code == 200:
            return response.json().get('login')
    except Exception as e:
        print(f"Warning: Could not fetch authenticated user: {e}")
    return None

def ensure_funding_yml(owner, repo, token, headers):
    """Checks for .github/FUNDING.yml and creates it if missing."""
    path = '.github/FUNDING.yml'
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
    
    # Check if it exists
    check_resp = requests.get(url, headers=headers)
    if check_resp.status_code == 200:
        print(f"Info: '{path}' already exists.")
        return
    
    # Create it if missing
    print(f"Action: Creating '{path}' with default owner sponsorship...")
    content = f"github: [{owner}]\n"
    encoded_content = base64.b64encode(content.encode()).decode()
    
    data = {
        "message": "docs: create FUNDING.yml to enable sponsor button",
        "content": encoded_content
    }
    
    put_resp = requests.put(url, headers=headers, json=data)
    if put_resp.status_code == 201:
        print(f"Success: Created '{path}'.")
    else:
        print(f"Warning: Could not create '{path}': {put_resp.text}")

def main():
    # Load .env file if it exists
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Enable a specific tab/feature for a GitHub repository.')
    parser.add_argument('tabname', help='Name of the tab to enable (e.g., Discussions, Wiki, Issues, Projects)')
    parser.add_argument('username', nargs='?', help='GitHub username/owner of the repo (default: current user or remote owner)')
    parser.add_argument('repo', nargs='?', help='Name of the repository (default: current git directory)')
    parser.add_argument('--token', dest='token', help='GitHub ADMIN_TOKEN (default: ADMIN_TOKEN from .env)')
    
    args = parser.parse_args()
    
    # Resolve Token
    token = args.token or os.getenv('ADMIN_TOKEN')
    if not token:
        print("Error: ADMIN_TOKEN not provided as argument and not found in .env")
        sys.exit(1)
        
    # Resolve Owner and Repo
    remote_owner, remote_repo = get_git_remote_info()
    
    owner = args.username or remote_owner
    if not owner:
        owner = get_authenticated_user(token)
        if not owner:
            print("Error: Could not determine GitHub username. Please provide it as an argument.")
            sys.exit(1)
            
    repo = args.repo or remote_repo
    if not repo:
        repo = os.path.basename(os.getcwd())
        print(f"Info: Using current directory name as repo: {repo}")

    # Map tab/button name to GitHub API fields
    tab_mapping = {
        'discussions': 'has_discussions',
        'wiki': 'has_wiki',
        'issues': 'has_issues',
        'projects': 'has_projects',
        'pages': 'has_pages',
        'sponsor': 'hasSponsorshipsEnabled',
        'sponsorship': 'hasSponsorshipsEnabled',
        'sponsorships': 'hasSponsorshipsEnabled',
        'template': 'is_template',
        'forking': 'allow_forking',
        'merge_commit': 'allow_merge_commit',
        'squash_merge': 'allow_squash_merge',
        'rebase_merge': 'allow_rebase_merge',
        'auto_merge': 'allow_auto_merge',
        'delete_branch_on_merge': 'delete_branch_on_merge'
    }
    
    normalized_tab = args.tabname.lower().replace(' ', '_').replace('-', '_')
    field = tab_mapping.get(normalized_tab)
    
    if not field:
        field = normalized_tab if normalized_tab.startswith(('has_', 'allow_', 'is_', 'delete_')) else f"has_{normalized_tab}"
        print(f"Notice: '{args.tabname}' is not in standard mapping, attempting to use field: '{field}'")

    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    # Sponsorship must be handled via GraphQL
    if field == 'hasSponsorshipsEnabled':
        print(f"Action: Enabling '{args.tabname}' via GraphQL mutation...")
        
        # 1. Get Repo Node ID
        repo_resp = requests.get(f'https://api.github.com/repos/{owner}/{repo}', headers=headers)
        if repo_resp.status_code != 200:
            print(f"Error: Could not fetch repo info: {repo_resp.text}")
            sys.exit(1)
        node_id = repo_resp.json().get('node_id')
        
        # 2. GraphQL Mutation
        query = """
        mutation($id: ID!, $enabled: Boolean!) {
          updateRepository(input: {repositoryId: $id, hasSponsorshipsEnabled: $enabled}) {
            repository {
              hasSponsorshipsEnabled
            }
          }
        }
        """
        variables = {"id": node_id, "enabled": True}
        
        gql_resp = requests.post('https://api.github.com/graphql', 
                                headers=headers, 
                                json={'query': query, 'variables': variables})
        
        if gql_resp.status_code == 200:
            result = gql_resp.json()
            if 'errors' in result:
                print(f"Error: GraphQL failed: {result['errors']}")
            else:
                print(f"Success: '{args.tabname}' is now enabled for {owner}/{repo}!")
                # Automatically create FUNDING.yml if missing
                ensure_funding_yml(owner, repo, token, headers)
        else:
            print(f"Error: GraphQL request failed: {gql_resp.text}")
            sys.exit(1)
            
    else:
        # REST API for everything else
        url = f'https://api.github.com/repos/{owner}/{repo}'
        data = {field: True}
        print(f"Action: Enabling '{args.tabname}' ({field}=True) via REST PATCH...")
        
        try:
            response = requests.patch(url, headers=headers, json=data)
            if response.status_code == 200:
                print(f"Success: '{args.tabname}' is now enabled for {owner}/{repo}!")
            elif response.status_code == 404:
                print(f"Error: Repository {owner}/{repo} not found or token lacks access.")
            elif response.status_code == 422:
                print(f"Error: Validation failed. '{field}' might not be a valid property or is already enabled.")
                print(f"Response: {response.json().get('message')}")
            else:
                print(f"Error: Failed with status code {response.status_code}")
                print(f"Response: {response.text}")
                sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error: Connection failed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()
