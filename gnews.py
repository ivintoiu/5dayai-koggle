#!/usr/bin/env python3
"""
Google News CLI Tool
Fetch, search, and read the latest news from Google News directly from your terminal.
"""

import sys
import os
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import html
import webbrowser
import json
import email.utils
from datetime import datetime, timezone
import concurrent.futures

# Initialize Windows virtual terminal processing for ANSI escape sequences
if os.name == 'nt':
    os.system('')

# Try importing rich for enhanced visual styling
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ANSI Color Fallbacks if rich is not installed
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GRAY = '\033[90m'

# Topic ID mapping for Google News RSS
TOPICS = {
    'world': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4d0FtVnVHZ0pWVXlnQVAB',
    'nation': 'CAAqIggKIhxDQkFTRVFvSUwyMHZNREpxTldad1pYUXdHZ0pWVXlnQVAB',
    'business': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdpc0FtVnVHZ0pWVXlnQVAB',
    'technology': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRxYW5RU0FtVnVHZ0pWVXlnQVAB',
    'science': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjN0FtVnVHZ0pWVXlnQVAB',
    'health': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNR3d5Y0cxN0FtVnVHZ0pWVXlnQVAB',
    'sports': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZlhCc0FtVnVHZ0pWVXlnQVAB',
    'entertainment': 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp3YW1jN0FtVnVHZ0pWVXlnQVAB'
}

def parse_title_source(title):
    """Split article title and source publication name."""
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), "Unknown"

def format_date(pub_date_str):
    """Convert RSS pubDate string to a human-friendly relative format."""
    try:
        parsed_dt = email.utils.parsedate_to_datetime(pub_date_str)
        now = datetime.now(timezone.utc)
        diff = now - parsed_dt
        
        if diff.days > 0:
            if diff.days == 1:
                return "Yesterday"
            return f"{diff.days} days ago"
        
        seconds = diff.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h ago"
        if minutes > 0:
            return f"{minutes}m ago"
        return "Just now"
    except Exception:
        return pub_date_str

def resolve_url(url):
    """Follow HTTP redirect to get the destination URL."""
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.geturl()
    except Exception:
        try:
            req = urllib.request.Request(url, method='GET', headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.geturl()
        except Exception:
            return url

def resolve_articles_urls(articles):
    """Concurrently resolve Google tracker URLs for a list of articles."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_article = {executor.submit(resolve_url, art['link']): art for art in articles}
        for future in concurrent.futures.as_completed(future_to_article):
            art = future_to_article[future]
            try:
                resolved_link = future.result()
                art['link'] = resolved_link
            except Exception:
                pass

def fetch_rss(url):
    """Download RSS feed XML content."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()
    except Exception as e:
        if HAS_RICH:
            Console().print(f"[bold red]Error fetching RSS feed:[/bold red] {e}")
        else:
            print(f"{Colors.FAIL}Error fetching RSS feed:{Colors.ENDC} {e}")
        return None

def parse_rss(xml_data):
    """Parse RSS XML content into list of articles."""
    articles = []
    if not xml_data:
        return articles
    try:
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            pub_date_elem = item.find('pubDate')
            source_elem = item.find('source')
            
            title = html.unescape(title_elem.text) if title_elem is not None else ""
            link = link_elem.text if link_elem is not None else ""
            pub_date_raw = pub_date_elem.text if pub_date_elem is not None else ""
            
            source_name = "Unknown"
            if source_elem is not None:
                source_name = html.unescape(source_elem.text) if source_elem.text else source_elem.get('url', 'Unknown')
            
            headline, source = parse_title_source(title)
            if source == "Unknown" and source_name != "Unknown":
                source = source_name

            articles.append({
                'headline': headline,
                'source': source,
                'link': link,
                'pubDate': pub_date_raw
            })
    except Exception as e:
        if HAS_RICH:
            Console().print(f"[bold red]Error parsing RSS XML:[/bold red] {e}")
        else:
            print(f"{Colors.FAIL}Error parsing RSS XML:{Colors.ENDC} {e}")
    return articles

def print_header():
    """Print the app header."""
    if HAS_RICH:
        console = Console()
        console.print(Panel(
            Text("Google News CLI", justify="center", style="bold cyan"),
            subtitle="Get the latest news directly in your terminal",
            style="cyan"
        ))
    else:
        print(f"{Colors.HEADER}{Colors.BOLD}" + "=" * 50)
        print("                Google News CLI")
        print("     Get the latest news directly in your terminal")
        print("=" * 50 + f"{Colors.ENDC}")

def display_articles(articles, topic_name):
    """Render article list with index numbers."""
    if HAS_RICH:
        console = Console()
        table = Table(
            title=f"\nGoogle News: [bold cyan]{topic_name.upper()}[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )
        table.add_column("#", style="bold yellow", width=4, justify="right")
        table.add_column("Headline", style="white")
        table.add_column("Source", style="green", width=20)
        table.add_column("Published", style="cyan", width=15)
        
        for idx, art in enumerate(articles, 1):
            table.add_row(
                str(idx),
                art['headline'],
                art['source'],
                format_date(art['pubDate'])
            )
        console.print(table)
    else:
        print(f"\n{Colors.HEADER}{Colors.BOLD}=== Google News: {topic_name.upper()} ==={Colors.ENDC}\n")
        for idx, art in enumerate(articles, 1):
            headline = art['headline']
            source = art['source']
            published = format_date(art['pubDate'])
            print(f"[{Colors.BOLD}{Colors.OKGREEN}{idx}{Colors.ENDC}] {Colors.OKCYAN}{headline}{Colors.ENDC}")
            print(f"    Source: {Colors.WARNING}{source}{Colors.ENDC} | Published: {Colors.GRAY}{published}{Colors.ENDC}")
            print(f"    Link: {Colors.GRAY}{art['link']}{Colors.ENDC}")
            print("-" * 60)

def fetch_and_show_articles(url, title, limit, resolve=False):
    """Fetch, process, and display articles."""
    if HAS_RICH:
        console = Console()
        with console.status("[cyan]Fetching news...[/cyan]"):
            xml_data = fetch_rss(url)
    else:
        print("Fetching news...")
        xml_data = fetch_rss(url)

    articles = parse_rss(xml_data)[:limit]
    if not articles:
        if HAS_RICH:
            Console().print("[bold red]No news articles found.[/bold red]")
        else:
            print(f"{Colors.FAIL}No news articles found.{Colors.ENDC}")
        return []

    if resolve:
        if HAS_RICH:
            Console().print("[cyan]Resolving article destination URLs...[/cyan]")
        else:
            print("Resolving article destination URLs...")
            
        resolve_articles_urls(articles)

    display_articles(articles, title)
    return articles

def interactive_loop(hl, gl, limit, resolve=False):
    """Main interactive terminal loop."""
    locale_params = f"hl={hl}&gl={gl}&ceid={gl}:{hl}"
    
    categories = [
        ("Top Headlines", f"https://news.google.com/rss?{locale_params}"),
        ("World News", f"https://news.google.com/rss/topics/{TOPICS['world']}?{locale_params}"),
        ("Business News", f"https://news.google.com/rss/topics/{TOPICS['business']}?{locale_params}"),
        ("Technology News", f"https://news.google.com/rss/topics/{TOPICS['technology']}?{locale_params}"),
        ("Science News", f"https://news.google.com/rss/topics/{TOPICS['science']}?{locale_params}"),
        ("Sports News", f"https://news.google.com/rss/topics/{TOPICS['sports']}?{locale_params}"),
        ("Health News", f"https://news.google.com/rss/topics/{TOPICS['health']}?{locale_params}"),
        ("Entertainment News", f"https://news.google.com/rss/topics/{TOPICS['entertainment']}?{locale_params}"),
        ("Custom Search", None)
    ]
    
    current_articles = []
    
    while True:
        print_header()
        
        # Display Menu
        if HAS_RICH:
            console = Console()
            menu_text = Text("\nSelect a news category:\n", style="bold")
            for idx, (cat_name, _) in enumerate(categories, 1):
                menu_text.append(f"  {idx}. ", style="bold yellow")
                menu_text.append(f"{cat_name}\n", style="white")
            menu_text.append(f"  q. ", style="bold red")
            menu_text.append("Exit\n", style="white")
            console.print(menu_text)
        else:
            print("\nSelect a news category:")
            for idx, (cat_name, _) in enumerate(categories, 1):
                print(f"  {Colors.BOLD}{Colors.OKGREEN}{idx}{Colors.ENDC}. {cat_name}")
            print(f"  {Colors.BOLD}{Colors.FAIL}q{Colors.ENDC}. Exit")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice.lower() == 'q':
            print("Goodbye!")
            break
            
        if not choice.isdigit() or not (1 <= int(choice) <= len(categories)):
            if HAS_RICH:
                Console().print("[bold red]Invalid option. Please try again.[/bold red]")
            else:
                print(f"{Colors.FAIL}Invalid option. Please try again.{Colors.ENDC}")
            continue
            
        selected_idx = int(choice) - 1
        cat_name, feed_url = categories[selected_idx]
        
        # Handling custom search
        if cat_name == "Custom Search":
            query = input("\nEnter search query: ").strip()
            if not query:
                continue
            query_encoded = urllib.parse.quote_plus(query)
            feed_url = f"https://news.google.com/rss/search?q={query_encoded}&{locale_params}"
            title = f"Search Results: {query}"
        else:
            title = cat_name
            
        # Fetch and show
        current_articles = fetch_and_show_articles(feed_url, title, limit, resolve)
        
        # Sub-loop for reading articles
        while current_articles:
            if HAS_RICH:
                prompt_str = "\n[bold yellow]Options:[/bold yellow] Enter article [bold green]# (1-n)[/bold green] to open, [bold cyan]'m'[/bold cyan] for Main Menu, [bold cyan]'r'[/bold cyan] to Refresh: "
                Console().print(prompt_str, end="")
            else:
                print(f"\n{Colors.BOLD}Options:{Colors.ENDC} Enter article {Colors.OKGREEN}# (1-{len(current_articles)}){Colors.ENDC} to open, {Colors.OKCYAN}'m'{Colors.ENDC} for Main Menu, {Colors.OKCYAN}'r'{Colors.ENDC} to Refresh: ", end="")
            
            sub_choice = input().strip().lower()
            
            if sub_choice == 'm':
                break
            elif sub_choice == 'r':
                current_articles = fetch_and_show_articles(feed_url, title, limit, resolve)
            elif sub_choice.isdigit():
                art_idx = int(sub_choice) - 1
                if 0 <= art_idx < len(current_articles):
                    art = current_articles[art_idx]
                    url_to_open = art['link']
                    
                    # If URL isn't resolved yet and user wants to read, we resolve it on the fly
                    # to make sure their web browser opens a direct/clean URL, although redirect works too
                    if "news.google.com" in url_to_open:
                        if HAS_RICH:
                            Console().print(f"[cyan]Resolving redirection for: {art['headline']}...[/cyan]")
                        else:
                            print(f"Resolving redirection for: {art['headline']}...")
                        url_to_open = resolve_url(url_to_open)
                        art['link'] = url_to_open  # cache resolved
                    
                    if HAS_RICH:
                        Console().print(f"[green]Opening in default browser:[/green] {art['headline']}")
                    else:
                        print(f"Opening in default browser: {art['headline']}")
                        
                    webbrowser.open(url_to_open)
                else:
                    if HAS_RICH:
                        Console().print("[bold red]Invalid article number.[/bold red]")
                    else:
                        print(f"{Colors.FAIL}Invalid article number.{Colors.ENDC}")
            else:
                if HAS_RICH:
                    Console().print("[bold red]Invalid option.[/bold red]")
                else:
                    print(f"{Colors.FAIL}Invalid option.{Colors.ENDC}")

def main():
    parser = argparse.ArgumentParser(
        description="Google News CLI - Fetch the latest news from Google News directly in your terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gnews.py                       # Launch interactive mode
  python gnews.py --topic technology    # Get latest technology news
  python gnews.py --search "AI Agents"  # Search for articles about AI Agents
  python gnews.py --limit 5 --json     # Output top 5 headlines as JSON
  python gnews.py --resolve --json      # Resolve final redirect links before output
"""
    )
    
    parser.add_argument("-s", "--search", help="Search query for articles")
    parser.add_argument(
        "-t", "--topic", 
        choices=['world', 'nation', 'business', 'technology', 'science', 'health', 'sports', 'entertainment'],
        help="Fetch articles for a specific topic category"
    )
    parser.add_argument("-l", "--limit", type=int, default=10, help="Number of articles to fetch (default: 10)")
    parser.add_argument("-j", "--json", action="store_true", help="Output results as JSON")
    parser.add_argument("-o", "--open", action="store_true", help="Automatically open the top article in browser")
    parser.add_argument("-lc", "--locale", default="US:en", help="Locale as Country:Language, e.g. US:en, GB:en, FR:fr (default: US:en)")
    parser.add_argument("-r", "--resolve", action="store_true", help="Resolve the final destination URL (instead of Google tracker link)")
    
    args = parser.parse_args()

    # Parse locale
    gl, hl = "US", "en"
    if args.locale and ":" in args.locale:
        gl, hl = args.locale.split(":", 1)

    # If no search query and no topic is specified, launch interactive mode
    if args.search is None and args.topic is None:
        interactive_loop(hl, gl, args.limit, args.resolve)
        return

    # Direct mode URL construction
    locale_params = f"hl={hl}&gl={gl}&ceid={gl}:{hl}"
    if args.search:
        query_encoded = urllib.parse.quote_plus(args.search)
        feed_url = f"https://news.google.com/rss/search?q={query_encoded}&{locale_params}"
        title = f"Search: {args.search}"
    else:
        topic_id = TOPICS[args.topic]
        feed_url = f"https://news.google.com/rss/topics/{topic_id}?{locale_params}"
        title = f"Topic: {args.topic}"

    # Fetch and parse
    xml_data = fetch_rss(feed_url)
    articles = parse_rss(xml_data)[:args.limit]

    if not articles:
        if args.json:
            print(json.dumps([]))
        else:
            print("No articles found.")
        return

    # Resolve links if requested
    if args.resolve:
        resolve_articles_urls(articles)

    # Output JSON or Render text
    if args.json:
        # Standardize representation for datetime values
        output_data = []
        for art in articles:
            output_data.append({
                'headline': art['headline'],
                'source': art['source'],
                'link': art['link'],
                'pubDate': art['pubDate'],
                'relativeDate': format_date(art['pubDate'])
            })
        print(json.dumps(output_data, indent=2))
    else:
        display_articles(articles, title)

    # Automatically open first item in browser if requested
    if args.open and articles:
        url_to_open = articles[0]['link']
        if "news.google.com" in url_to_open and args.resolve is False:
            url_to_open = resolve_url(url_to_open)
        if HAS_RICH:
            Console().print(f"\n[green]Automatically opening top article:[/green] {articles[0]['headline']}")
        else:
            print(f"\nAutomatically opening top article: {articles[0]['headline']}")
        webbrowser.open(url_to_open)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
