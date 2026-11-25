# S23 RTL session log

Times are IST (UTC+05:30), 25 Nov 2026.

- 14:37: Samsung RTL reservation started for Galaxy S23 SM-S911B-IN3, Android 14, 30 minutes.
- 14:40: RDB connected. ADB probe identifies SM-S911B, Qualcomm SM8550, Android 14, arm64-v8a.
- APK SHA-256: `88f6a53285c04ef8e0fb7766b05da716dbdc22a4b11112e731b70165e3d07862` (CI run 45398563324).
- Host model SHA-256: `ab7b7ebf97421c7770ad97d4abfdf8650a7d9f9dc1ce9a0c4663d49f7b7a08ac`; tokenizer SHA-256: `82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55`.
- 14:40–14:48: ADB install timed out after 180 seconds; the Samsung web client transfer also failed to progress. A trial upload of the model was cancelled and removed. No device-side model hash was obtained.
- 14:52: Package inventory found all eight named screen-sharing apps absent; this does not establish whether the app banner behaves correctly.
- 14:56: After reconnecting RDB, a direct APK push was attempted. The device-side partial file grew from 1,376,256 bytes at 14:56:32 to 4,784,128 bytes at 14:57:05, far slower than the prior session. The 1.1 GiB model could not be staged and verified within the remaining time at this observed rate.
- 15:03: The direct APK push reached 34,603,008 bytes of 48,283,077 and was stopped to leave time for cleanup. Prahari was never installed. The device reported airplane mode `0`, screen timeout restored to `300000` ms, no `in.prahari.app` package, and the partial APK and model files absent.
- 15:04: RTL web client reported “All ongoing tests have ended.” The reservation page subsequently showed the device “Getting ready to restart”; its final release status is reported separately.
- 15:05: RDB stopped and the local Hindsight API service restarted; port 8888 was again listening on the Hindsight API.
- 15:06: Samsung Developer showed the Sign in link. Browser policy blocked access to site-data settings, so cookie clearing was not verified or completed.
- 15:08: After the account instruction changed, the dedicated Samsung account was signed in again. The reservation list showed “No devices detected!” Site data was left intact.

## Retry on a different unit

- 15:12: With 80 RTL credits available, reserved Android 14 Galaxy S23 `SM-S911B-IN4` for 30 minutes; the balance became 78 credits.
- The RTL client repeatedly timed out while opening Remote Debug Bridge. Reloading the unresponsive view ended the live test; Samsung then showed “Getting ready to restart” and temporarily disabled re-entry. Re-entered the same reservation without additional credits once Start became available.
- The re-entered RTL client again timed out on the bridge control and screenshots. ADB never listed the device. The 5 MiB transfer probe therefore could not run and no throughput value was measured; neither the APK nor the model was sent to this unit.
- 15:28: The web client reported “All ongoing tests have ended.” RDB was stopped and the Hindsight service restarted. The reservation was still in Samsung's restart state while attempting return.
- 15:32: Samsung's Return device action completed, and Reservations showed “No devices detected!”. Hindsight was active and listening on port 8888; the Samsung account remained signed in.
