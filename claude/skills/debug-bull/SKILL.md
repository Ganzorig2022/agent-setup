---
name: debug-bull
description: Diagnose and fix Bull queue problems in QPay services — failed jobs, stalled jobs, jobs not processing, queue backed up, workers not running. Use when a Bull queue is misbehaving.
---

# Debug Bull Queue — QPay

QPay uses Bull 4.x with Redis. Queues live in `src/queues/` with separate producer and consumer files.

## Step 1: Check Redis First

Bull is a Redis-backed queue. If Redis is down or unreachable, nothing works.

```bash
redis-cli ping          # should return PONG
redis-cli info server   # check version and uptime
```

If Redis is unavailable, no amount of queue debugging will help. Fix Redis first.

## Step 2: Inspect Queue State

```js
// Add this temporarily to check queue health
const Queue = require('bull')
const queue = new Queue('queue-name', { redis: redisConfig })

const [waiting, active, completed, failed, delayed] = await Promise.all([
  queue.getWaitingCount(),
  queue.getActiveCount(),
  queue.getCompletedCount(),
  queue.getFailedCount(),
  queue.getDelayedCount(),
])
console.log({ waiting, active, completed, failed, delayed })
```

## Step 3: Read Failed Jobs

Failed jobs contain the original data and the error that caused failure.

```js
const failedJobs = await queue.getFailed(0, 10)
failedJobs.forEach(job => {
  console.log('Job data:', job.data)
  console.log('Failed reason:', job.failedReason)
  console.log('Stack:', job.stacktrace)
})
```

**Common failure patterns:**
- `UnhandledPromiseRejection` in the processor — async error not caught
- `Job stalled` — processor took longer than `lockDuration` (default 30s); increase it or fix the slow processor
- `ECONNREFUSED` — DB or external service down during processing
- `Validation error` — job data shape changed but processor not updated

## Step 4: Check the Consumer (Processor)

```
src/queues/<name>.consumer.js   # processor lives here
```

- Is `queue.process()` actually called? Check the consumer is imported and started
- Is the processor wrapped in try/catch? Uncaught throws cause stalled jobs
- Does the processor return a resolved promise? Forgetting `return` or `await` stalls the job
- Check concurrency setting — too low = backed up queue; too high = DB/Redis overload

```js
// Common mistake: forgetting await causes job to "complete" before work is done
queue.process(async (job) => {
  await doActualWork(job.data)   // must await
})
```

## Step 5: Check Stalled Jobs

Stalled = job was picked up but the worker crashed or timed out before completing.

```js
// Bull automatically moves stalled jobs back to waiting after stalledInterval
// Check if stalledInterval and lockDuration are configured correctly
const queue = new Queue('name', {
  settings: {
    lockDuration: 30000,       // max ms a job can run before considered stalled
    stalledInterval: 30000,    // how often to check for stalled jobs
    maxStalledCount: 1,        // retries before marking as failed
  }
})
```

If jobs keep stalling, the processor is taking too long — optimize it or increase `lockDuration`.

## Step 6: Retry or Clean Failed Jobs

```js
// Retry a specific failed job
const job = await queue.getJob(jobId)
await job.retry()

// Retry all failed jobs
const failedJobs = await queue.getFailed()
await Promise.all(failedJobs.map(job => job.retry()))

// Clean old completed/failed jobs to free Redis memory
await queue.clean(24 * 60 * 60 * 1000, 'completed')   // older than 24h
await queue.clean(7 * 24 * 60 * 60 * 1000, 'failed')  // older than 7d
```

## Step 7: Check Producer

If no jobs are appearing at all, the problem may be in the producer, not the consumer.

```
src/queues/<name>.producer.js
```

- Is `queue.add(data, opts)` actually called?
- Is the queue name exactly the same in producer and consumer?
- Check the Redis key: `bull:<queue-name>:waiting` should grow when jobs are added

## Common Fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Jobs stuck in `waiting`, never `active` | Consumer not running | Import and start the consumer |
| Jobs going `active` then back to `waiting` | Stalled — processor too slow | Increase `lockDuration` or optimize processor |
| Jobs `failed` immediately | Uncaught error in processor | Wrap processor in try/catch, check `failedReason` |
| Queue backed up | Concurrency too low | Increase `queue.process(concurrency, fn)` |
| Jobs processed multiple times | Multiple consumer instances | Check deployment — how many workers are running? |
