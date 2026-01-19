/**
 * API Cache Module
 * Prevents duplicate API calls by caching responses
 */

const apiCache = {
    cache: new Map(),
    pendingRequests: new Map(),

    /**
     * Fetch with caching and deduplication
     * @param {string} url - API endpoint
     * @param {number} ttl - Time to live in milliseconds (default: 5 minutes)
     * @returns {Promise} - Cached or fresh data
     */
    async fetch(url, ttl = 300000) {
        // Check cache first
        const cached = this.cache.get(url);
        if (cached && Date.now() - cached.timestamp < ttl) {
            console.log(`[Cache HIT] ${url}`);
            return Promise.resolve(cached.data);
        }

        // Check if request is already pending
        if (this.pendingRequests.has(url)) {
            console.log(`[Cache PENDING] ${url}`);
            return this.pendingRequests.get(url);
        }

        // Make new request
        console.log(`[Cache MISS] ${url}`);
        const promise = fetch(url)
            .then(response => response.json())
            .then(data => {
                // Store in cache
                this.cache.set(url, {
                    data: data,
                    timestamp: Date.now()
                });

                // Remove from pending
                this.pendingRequests.delete(url);

                return data;
            })
            .catch(error => {
                // Remove from pending on error
                this.pendingRequests.delete(url);
                throw error;
            });

        // Store pending request
        this.pendingRequests.set(url, promise);

        return promise;
    },

    /**
     * Clear cache for a specific URL or all cache
     * @param {string} url - Optional URL to clear, if not provided clears all
     */
    clear(url = null) {
        if (url) {
            this.cache.delete(url);
            this.pendingRequests.delete(url);
        } else {
            this.cache.clear();
            this.pendingRequests.clear();
        }
    },

    /**
     * Invalidate cache when year changes
     */
    invalidateYear() {
        // Clear all estadisticas and chart endpoints
        for (const key of this.cache.keys()) {
            if (key.includes('/api/')) {
                this.cache.delete(key);
            }
        }
    }
};

// Export for use in other scripts
window.apiCache = apiCache;
