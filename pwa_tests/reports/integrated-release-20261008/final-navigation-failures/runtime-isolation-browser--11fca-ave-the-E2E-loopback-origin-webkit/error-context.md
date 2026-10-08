# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: runtime-isolation.spec.ts >> browser HTTP and WebSocket traffic cannot leave the E2E loopback origin
- Location: e2e/runtime-isolation.spec.ts:364:1

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: Expected network-guard probes were not observed

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 4

- Array []
+ Array [
+   "https://network-probe.example.invalid/e2e-fetch",
+   "wss://network-probe.example.invalid/e2e-websocket",
+ ]
```

```
Tearing down "context" exceeded the test timeout of 30000ms.
```