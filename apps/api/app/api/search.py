from fastapi import APIRouter, HTTPException, Query
import httpx
from bs4 import BeautifulSoup
import asyncio

router = APIRouter()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

async def search_google(query: str):
    """Perform a Google search and return the results."""
    search_url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": USER_AGENT}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(search_url, headers=headers, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error occurred: {e}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error occurred: {e}")

    soup = BeautifulSoup(response.text, "html.parser")
    
    results = []
    for g in soup.find_all('div', class_='g'):
        title_element = g.find('h3')
        link_element = g.find('a')
        snippet_element = g.find('div', style="display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; text-overflow: ellipsis;")

        if title_element and link_element:
            title = title_element.text
            link = link_element['href']
            snippet = snippet_element.text if snippet_element else ""
            
            if link.startswith("/url?q="):
                link = link.split("/url?q=")[1].split("&sa=")[0]

            results.append({"title": title, "link": link, "snippet": snippet})
            
    return results

@router.get("/api/search")
async def get_search_results(q: str = Query(..., description="The search query.")):
    """
    Perform a Google search and return the results in JSON format.
    """
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")
    
    try:
        search_results = await search_google(q)
        return {"results": search_results}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

