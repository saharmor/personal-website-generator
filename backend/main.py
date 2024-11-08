from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

import os
from anthropic import Anthropic
from dotenv import load_dotenv
import uvicorn
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WebsiteRequest(BaseModel):
    github_url: str
    color_palette: str
    layout: str

async def fetch_github_data(username: str) -> dict:
    """
    Fetch repositories for a given GitHub username.
    
    Args:
        username (str): GitHub username
    
    Returns:
        list: List of repositories with their details
    """
    # GitHub API endpoint
    url = f"https://api.github.com/users/{username}/repos"
    
    try:
        # Send GET request to GitHub API
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Extract relevant information from each repository
        repos = []
        for repo in response.json():
            repos.append({
                'name': repo['name'],
                'stars': repo['stargazers_count'],
                'description': repo['description'] or 'No description',
                'language': repo['language'] or 'Not specified',
                'last_updated': repo['updated_at'][:10]  # Just the date part
            })
        
        # Sort repositories by stars (descending)
        repos.sort(key=lambda x: x['stars'], reverse=True)
        # Get user profile data
        profile_url = f"https://api.github.com/users/{username}"
        profile_response = requests.get(profile_url)
        profile_response.raise_for_status()
        profile_data = profile_response.json()
        
        # Combine profile and repos data
        github_data = {
            'profile': {
                'name': profile_data.get('name', username),
                'login': username,
                'bio': profile_data.get('bio', ''),
                'avatar_url': profile_data.get('avatar_url', ''),
                'location': profile_data.get('location', ''),
                'blog': profile_data.get('blog', ''),
                'twitter_username': profile_data.get('twitter_username', ''),
                'public_repos': profile_data.get('public_repos', 0)
            },
            'repositories': repos
        }
        return github_data
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching repositories: {e}")
        return None
    except KeyError as e:
        print(f"Error parsing repository data: {e}")
        return None

    

async def generate_website_content(github_data: dict, color_palette: str, layout: str) -> str:
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Prepare the prompt for Claude
    prompt = f"""Generate a modern, responsive HTML/CSS website based on the following GitHub profile:
    User: {github_data['profile']['name']} ({github_data['profile']['login']})
    Bio: {github_data['profile']['bio']}
    Color Palette: {color_palette}
    Layout Style: {layout}
    
    Top Repositories:
    | Repository | Stars | Description | Language | Last Updated |
    | --- | --- | --- | --- | --- |
    {'\n'.join([
        f"| {repo['name']} | {repo['stars']} | {repo['description']} | {repo['language']} | {repo['last_updated']} |" 
        for repo in github_data['repositories'][:5]
    ])}
    
    Generate a complete HTML file with embedded CSS that creates a professional portfolio website.
    Use the specified color palette and layout style.
    """
    
    message = await anthropic.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    
    return message.content

@app.post("/api/generate")
async def generate_website(request: WebsiteRequest):
    """
    Example usage:
    POST http://localhost:8000/api/generate
    {
        "github_url": "https://github.com/torvalds",
        "color_palette": "modern",
        "layout": "minimal"
    }
    """
    try:
        # Extract username from GitHub URL
        username = request.github_url.split('/')[-1]
        
        # Fetch GitHub data
        github_data = await fetch_github_data(username)
        
        # Generate website content
        website_content = await generate_website_content(
            github_data,
            request.color_palette,
            request.layout
        )
        
        return {"content": website_content}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
