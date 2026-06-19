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

def ensure_discussion_template(owner, repo, token, headers):
    """Checks for .github/DISCUSSION_TEMPLATE/announcements.yml and creates it if missing."""
    path = '.github/DISCUSSION_TEMPLATE/announcements.yml'
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
    
    # Check if it exists
    check_resp = requests.get(url, headers=headers)
    if check_resp.status_code == 200:
        print(f"Info: '{path}' already exists.")
        return
    
    # Create it if missing
    print(f"Action: Creating '{path}' with welcome_text template...")
    content = """title: Announcements
body:
  - type: textarea
    id: welcome_text
    attributes:
      label: Welcome Text
      description: Welcome text for this announcement.
      placeholder: Write something here...
    validations:
      required: true
"""
    encoded_content = base64.b64encode(content.encode()).decode()
    
    data = {
        "message": "docs: create announcements template for discussions",
        "content": encoded_content
    }
    
    put_resp = requests.put(url, headers=headers, json=data)
    if put_resp.status_code == 201:
        print(f"Success: Created '{path}'.")
    else:
        print(f"Warning: Could not create '{path}': {put_resp.text}")

def create_welcome_discussion(owner, repo, token, headers):
    """Creates a welcome discussion post in the Announcements category if it doesn't already exist."""
    # 1. Fetch Repository Node ID, Categories, and recent Discussions
    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        id
        discussionCategories(first: 20) {
          nodes {
            id
            name
            slug
          }
        }
        discussions(first: 30, orderBy: {field: CREATED_AT, direction: DESC}) {
          nodes {
            title
            category {
              slug
            }
          }
        }
      }
    }
    """
    variables = {"owner": owner, "repo": repo}
    gql_url = 'https://api.github.com/graphql'
    
    print(f"Action: Checking for existing welcome discussion in {owner}/{repo}...")
    try:
        resp = requests.post(gql_url, headers=headers, json={'query': query, 'variables': variables})
        if resp.status_code != 200:
            print(f"Warning: GraphQL request failed to fetch repository details: {resp.text}")
            return
            
        res_data = resp.json()
        if 'errors' in res_data:
            print(f"Warning: GraphQL returned errors: {res_data['errors']}")
            return
            
        repo_data = res_data.get('data', {}).get('repository')
        if not repo_data:
            print("Warning: Could not fetch repository data from GraphQL.")
            return
            
        repo_node_id = repo_data.get('id')
        categories = repo_data.get('discussionCategories', {}).get('nodes', [])
        discussions = repo_data.get('discussions', {}).get('nodes', [])
        
        # Check if welcome discussion already exists
        target_title = "Welcome to our discussions!"
        for disc in discussions:
            disc_title = disc.get('title')
            disc_cat = disc.get('category', {})
            if disc_title == target_title and disc_cat.get('slug') == 'announcements':
                print(f"Info: Welcome discussion '{target_title}' already exists in Announcements.")
                return
        
        # Find Announcements Category ID
        announcements_category_id = None
        for cat in categories:
            if cat.get('slug') == 'announcements' or cat.get('name', '').lower() == 'announcements':
                announcements_category_id = cat.get('id')
                break
                
        if not announcements_category_id:
            print("Warning: 'Announcements' category not found in repository discussions.")
            return
            
        # 2. Create the discussion
        print(f"Action: Creating a new welcome discussion post in Announcements category...")
        mutation = """
        mutation($repoId: ID!, $catId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {repositoryId: $repoId, categoryId: $catId, title: $title, body: $body}) {
            discussion {
              id
              url
              title
            }
          }
        }
        """
        
        body = (
            "# Welcome to our Discussions tab! \ud83d\udc4b\n\n"
            "We are excited to have you here! This is a space for our community to:\n\n"
            "- \ud83d\udcac **Ask questions** about how to use the project or get help.\n"
            "- \ud83d\udca1 **Share ideas** and feature requests.\n"
            "- \ud83d\udce2 **Get announcements** and updates on new releases.\n"
            "- \ud83e\udd1d **Connect** with other community members and maintainers.\n\n"
            "To get started, feel free to introduce yourself in the comments below!"
        )
        
        mut_variables = {
            "repoId": repo_node_id,
            "catId": announcements_category_id,
            "title": target_title,
            "body": body
        }
        
        mut_resp = requests.post(gql_url, headers=headers, json={'query': mutation, 'variables': mut_variables})
        if mut_resp.status_code == 200:
            mut_data = mut_resp.json()
            if 'errors' in mut_data:
                print(f"Warning: GraphQL failed to create discussion: {mut_data['errors']}")
            else:
                disc = mut_data.get('data', {}).get('createDiscussion', {}).get('discussion', {})
                print(f"Success: Created welcome discussion: {disc.get('title')} - {disc.get('url')}")
        else:
            print(f"Warning: GraphQL request to create discussion failed: {mut_resp.text}")
            
    except Exception as e:
        print(f"Warning: Could not create welcome discussion: {e}")

def main():
    # Load .env file if it exists
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Enable a specific tab/feature for a GitHub repository.')
    parser.add_argument('tabname', help='Name of the tab to enable (e.g., Discussions, Wiki, Issues, Projects)')
    parser.add_argument('username', nargs='?', help='GitHub username/owner of the repo (default: current user or remote owner)')
    parser.add_argument('repo', nargs='?', help='Name of the repository (default: current git directory)')
    parser.add_argument('--token', dest='token', help='GitHub ADMIN_TOKEN (default: ADMIN_TOKEN from .env)')
    parser.add_argument('--discussion-template', action='store_true', help='Create a default welcome_text template in announcements category')
    
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
                if field == 'has_discussions' and args.discussion_template:
                    ensure_discussion_template(owner, repo, token, headers)
                    create_welcome_discussion(owner, repo, token, headers)
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
