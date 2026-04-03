# PolitmaTrader X Poster

Lightweight microservice that receives webhooks from the PolitmaTrader marketing system and posts to X (Twitter).

## How it works

1. Marketing system sends POST to `/post` with content payload
2. 2. This service builds the tweet from hook + body + cta + hashtags
   3. 3. Signs the request with OAuth 1.0a
      4. 4. Posts to X API v2
         5. 5. Returns the tweet ID
           
            6. ## Deploy to Railway with Claude Code
           
            7. Open Claude Code in this directory and paste:
           
            8. ```
               Deploy this X posting service to Railway:
               1. Initialize git and push to a new GitHub repo called politmatrader-xposter
               2. Deploy to Railway using the railway CLI
               3. Set these env vars in Railway (I'll provide the values):
                  - X_API_KEY
                  - X_API_SECRET
                  - X_ACCESS_TOKEN
                  - X_ACCESS_TOKEN_SECRET
               4. Test by hitting /health to confirm it's running
               ```

               ## Endpoints

               - `GET /` - status check
               - - `GET /health` - health check with credential status
                 - - `POST /post` - receives marketing system payload, posts to X
