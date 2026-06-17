# GitHub Tabs CLI

A command-line tool to enable GitHub repository tabs (e.g., Discussions, Wiki) and buttons (e.g., Sponsorships) via the GitHub API.

## Features

- **Enable Tabs:** Discussions, Wiki, Issues, Projects, Pages.
- **Enable Buttons:** Sponsorships (automatically creates `.github/FUNDING.yml` if missing), Template mode, Forking.
- **Merge Settings:** Squash merge, Rebase merge, Auto-merge.
- **Auto-Detection:** Automatically detects repository owner and name from the current git directory.
- **Smart Defaults:** Fetches the authenticated user from the token if no username is provided.

## Installation

You can install the tool locally from the source:

```bash
pip install .
```

## Usage

Once installed, you can run the tool using the `github-tabs` command.

### Configuration

Create a `.env` file in your project root or set an environment variable:

```env
ADMIN_TOKEN=your_github_personal_access_token
```

### Examples

Enable **Discussions**:
```bash
github-tabs Discussions
```

Enable **Sponsorships** (and auto-create FUNDING.yml):
```bash
github-tabs Sponsorships
```

Enable **Wiki** for a specific repository:
```bash
github-tabs Wiki username repo-name
```

Enable **Auto-Merge**:
```bash
github-tabs auto-merge
```

## Options

```bash
github-tabs [-h] [--token TOKEN] tabname [username] [repo]
```

- `tabname`: Name of the tab/button to enable.
- `username` (optional): GitHub owner of the repo.
- `repo` (optional): Name of the repository.
- `--token` (optional): GitHub ADMIN_TOKEN (overrides `.env`).
