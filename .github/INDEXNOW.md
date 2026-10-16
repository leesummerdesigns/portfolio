# Search update notifications

Changes pushed to `main` notify IndexNow about canonical pages whose HTML changed.
The job waits until the public files match the commit before sending the request.
Added and deleted canonical pages are supported through the current and previous
sitemaps. Noncanonical variants, local evidence and unrelated assets are excluded.

The root text file is the protocol's public site-ownership proof. It is separate
from GitHub credentials. The workflow has read-only repository permission and
does not pass a GitHub token to the notification endpoint.

To inspect the next notification without submitting:

```sh
python3 scripts/notify_indexnow.py --before HEAD^ --after HEAD --dry-run
```

The workflow can be retried through Actions. A manual run examines the latest
commit. If publication fails or a newer deployment replaces the expected files,
the job fails instead of reporting an unverified submission.

HTTP 200 confirms receipt. HTTP 202 confirms receipt with ownership validation
pending. Neither confirms indexing or ranking. Google indexing requests remain
separate from IndexNow.

Protocol: https://www.indexnow.org/documentation
