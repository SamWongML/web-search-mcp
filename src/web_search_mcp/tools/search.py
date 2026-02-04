"""Web search tool for MCP."""

from mcp.server.fastmcp import Context, FastMCP

from web_search_mcp.config import settings
from web_search_mcp.models.scrape import ScrapeOptions, ScrapeResult
from web_search_mcp.models.search import SearchResponse


async def _attach_scrapes(
    result_dict: dict,
    scrape_opts: dict | ScrapeOptions,
    max_scrape_results: int | None,
    app_ctx: "AppContext",
) -> dict:
    import anyio

    # Normalize scrape options
    if isinstance(scrape_opts, ScrapeOptions):
        options = scrape_opts
    else:
        options = ScrapeOptions(**scrape_opts)
    options = options.apply_defaults()

    results = result_dict.get("results", [])
    if not results:
        return result_dict

    if max_scrape_results is not None:
        max_scrape_results = max(1, min(100, max_scrape_results))

    max_allowed = min(
        len(results),
        max_scrape_results or len(results),
        settings.search_scrape_max_concurrent,
    )

    semaphore = anyio.Semaphore(settings.search_scrape_max_concurrent)

    async def scrape_one(idx: int, url: str) -> None:
        cache_key_params = {
            "include_links": options.include_links,
            "include_images": options.include_images,
            "use_browser": options.use_browser,
            "formats": options.formats or [],
            "only_main_content": options.only_main_content,
            "include_tags": options.include_tags,
            "exclude_tags": options.exclude_tags,
            "wait_for_selector": options.wait_for_selector,
            "max_length": options.max_length,
        }

        async with semaphore:
            cached = await app_ctx.cache.get_scrape(
                url,
                max_age_seconds=options.max_age_seconds,
                **cache_key_params,
            )
            if cached:
                cached["cached"] = True
                results[idx]["scrape"] = cached
                return

            scrape_result: ScrapeResult = await app_ctx.scraper.scrape(url, options=options)
            scrape_dict = scrape_result.model_dump()

            if scrape_result.success:
                await app_ctx.cache.set_scrape(url, scrape_dict, **cache_key_params)

            results[idx]["scrape"] = scrape_dict

    async with anyio.create_task_group() as tg:
        for i, item in enumerate(results[:max_allowed]):
            url = item.get("url")
            if not url:
                continue
            tg.start_soon(scrape_one, i, url)

    result_dict["results"] = results
    return result_dict


def register(mcp: FastMCP) -> None:
    """Register the web_search tool with the MCP server."""

    @mcp.tool()
    async def web_search(
        query: str,
        max_results: int = 10,
        language: str | None = None,
        region: str | None = None,
        safe_search: bool = True,
        time_range: str | None = None,
        location: str | None = None,
        country: str | None = None,
        sources: list[str] | None = None,
        categories: list[str] | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        search_depth: str | None = None,
        topic: str | None = None,
        scrape_options: dict | ScrapeOptions | None = None,
        max_scrape_results: int | None = None,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """
        Search the web and return results with links, titles, and metadata.

        Uses multiple search providers with automatic fallback:
        1. SerpAPI (if configured)
        2. Tavily Search (if configured)
        3. Brave Search (if configured)
        4. DuckDuckGo (always available)

        Args:
            query: Search query string (required)
            max_results: Maximum number of results to return (1-100, default: 10)
            language: Language code (e.g., "en")
            region: Region code (e.g., "us")
            safe_search: Enable safe search filtering
            time_range: Time range filter (provider-specific)
            location: Location string (provider-specific)
            country: Country code (provider-specific)
            sources: Preferred sources list
            categories: Category filters
            include_domains: Domains to include
            exclude_domains: Domains to exclude
            search_depth: Search depth (provider-specific)
            topic: Topic filter (provider-specific)
            scrape_options: Optional scrape options per result
            max_scrape_results: Max results to scrape (defaults to max_results, capped)

        Returns:
            Search results with URLs, titles, snippets, and metadata
        """
        from web_search_mcp.server import AppContext

        # Get app context from lifespan
        app_ctx: AppContext = ctx.request_context.lifespan_context

        cache_params = {
            "language": language,
            "region": region,
            "safe_search": safe_search,
            "time_range": time_range,
            "location": location,
            "country": country,
            "sources": sources or [],
            "categories": categories or [],
            "include_domains": include_domains or [],
            "exclude_domains": exclude_domains or [],
            "search_depth": search_depth,
            "topic": topic,
        }

        # Check cache first
        cached = await app_ctx.cache.get_search(query, max_results, **cache_params)
        if cached:
            cached["cached"] = True
            if scrape_options:
                cached = await _attach_scrapes(
                    cached,
                    scrape_options,
                    max_scrape_results,
                    app_ctx,
                )
            return cached

        # Perform search
        response: SearchResponse = await app_ctx.provider_registry.search(
            query=query,
            max_results=max_results,
            language=language,
            region=region,
            safe_search=safe_search,
            time_range=time_range,
            location=location,
            country=country,
            sources=sources,
            categories=categories,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            search_depth=search_depth,
            topic=topic,
        )

        # Convert to dict for response
        result = response.model_dump()

        # Cache the result
        await app_ctx.cache.set_search(query, max_results, result, **cache_params)

        # Attach scrapes if requested
        if scrape_options:
            result = await _attach_scrapes(result, scrape_options, max_scrape_results, app_ctx)

        return result
