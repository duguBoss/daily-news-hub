"""News deduplication and filtering utilities."""
from __future__ import annotations

import re
from typing import Any


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Convert to lowercase and remove punctuation
    text = text.lower()
    # Remove common punctuation and whitespace
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text


def _extract_keywords(text: str) -> set[str]:
    """Extract significant keywords from text."""
    # Common stop words to ignore
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
        'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
        'until', 'while', 'what', 'which', 'who', 'whom', 'this',
        'that', 'these', 'those', 'am', 'it', 'its', 'says', 'said',
        'say', 'new', 'news', 'report', 'reports', 'reported',
        'update', 'breaking', 'latest', 'today', 'yesterday',
    }
    
    words = _normalize_text(text).split()
    # Filter out stop words and short words
    return {w for w in words if len(w) > 2 and w not in stop_words}


def _calculate_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two texts."""
    keywords1 = _extract_keywords(text1)
    keywords2 = _extract_keywords(text2)
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    
    return intersection / union if union > 0 else 0.0


def _is_similar_article(article1: dict[str, Any], article2: dict[str, Any], threshold: float = 0.6) -> bool:
    """Check if two articles are similar based on title and summary."""
    # Compare titles
    title_sim = _calculate_similarity(
        article1.get('title', ''),
        article2.get('title', '')
    )
    
    # Compare summaries if available
    summary_sim = _calculate_similarity(
        article1.get('summary', ''),
        article2.get('summary', '')
    )
    
    # Use the higher similarity score
    max_sim = max(title_sim, summary_sim)
    
    return max_sim >= threshold


def deduplicate_news_items(
    items: list[dict[str, Any]], 
    max_articles: int = 5,
    similarity_threshold: float = 0.6
) -> list[dict[str, Any]]:
    """Remove similar news items and limit to max articles.
    
    Args:
        items: List of news items
        max_articles: Maximum number of articles to return
        similarity_threshold: Threshold for considering articles similar (0-1)
    
    Returns:
        Filtered list of unique news items
    """
    if not items:
        return []
    
    unique_items: list[dict[str, Any]] = []
    
    for item in items:
        # Check if this item is similar to any already selected item
        is_duplicate = False
        for selected in unique_items:
            if _is_similar_article(item, selected, similarity_threshold):
                is_duplicate = True
                print(f"  Filtered similar article: {item.get('title', '')[:50]}...")
                break
        
        if not is_duplicate:
            unique_items.append(item)
            
        # Stop once we have enough unique articles
        if len(unique_items) >= max_articles:
            break
    
    print(f"Deduplication: {len(items)} -> {len(unique_items)} unique articles")
    return unique_items


def filter_news_items(
    items: list[dict[str, Any]],
    max_articles: int = 5
) -> list[dict[str, Any]]:
    """Filter news items to remove duplicates and limit count.
    
    This is the main entry point for news filtering.
    """
    return deduplicate_news_items(items, max_articles=max_articles)
