# Task 001bu Summary — Feed Slice Rejection: Status Banner and Data Replacement

Implemented status banner notifications and replacement data upload flows in the feed workspace.

## Details
1. **API Client Integration**: Wired `resubmitFeedSlice` in `feeds-api.ts` pointing to `POST /sources/{id}/slices/{sliceId}/resubmit`.
2. **Status Banners**:
   - **`pending_approval`**: Shows an amber warning banner informing users that the field mapping analysis will block until approval clears.
   - **`rejected`**: Shows a red warning banner displaying `approvalRejectionReason` alongside a file selector and "Upload replacement" submit button.
3. **Data Replacement & Quiet Uploads**:
   - Uploading a replacement file in `rejected` status correctly triggers a new slice creation, re-loading the feed workspace under `pending_approval` state.
   - **`approved`**: Renders a clean "Upload a corrected file to replace this slice" upload form at the bottom of the Slice Panel card for correcting late-discovered data gaps.
4. **Dynamic Badges**: Replaced the hardcoded "received" status badge in the Slice Panel with a status-aware badge rendering `approved` (emerald), `rejected` (red), and `pending approval` (amber).
5. **Tests**: Added three comprehensive Vitest cases:
   - `renders pending approval banner when latest slice is pending_approval`
   - `renders rejection banner with upload replacement form when latest slice is rejected`
   - `renders quiet replacement upload control when latest slice is approved`
