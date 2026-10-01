from threading import BoundedSemaphore

from app.config import settings

# Held around anything that parses a file, computes a dashboard, or runs a recipe.
# Each takes a few times its frame's size while it works, so this is what keeps a
# burst of requests from adding up past the container's memory. The GIL already
# lets only one of them compute at a time, so waiting here costs little speed.
#
# Always taken before the store's or the dashboard cache's locks, never while
# holding one, so a request waiting for a slot can never block one that has it.
job_slots = BoundedSemaphore(settings.max_concurrent_jobs)
