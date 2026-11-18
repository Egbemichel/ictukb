/**
 * Google Apps Script: push a sheet change to the knowledge base immediately.
 *
 * Setup (once per Google Sheet):
 *   1. Extensions > Apps Script, paste this file.
 *   2. Project Settings > Script properties: add KB_API_URL (for example https://kb.example.org),
 *      KB_ADMIN_TOKEN (the ADMIN_TOKEN of the API) and KB_SHEET_NAME (the name used in sources/sheets.yml).
 *   3. Triggers > Add trigger > function notifyKnowledgeBase, event source "From spreadsheet",
 *      event type "On change". An installable trigger is required because a simple onEdit
 *      trigger is not allowed to call external services.
 *
 * Changes are debounced to one request per 20 seconds so that a burst of edits produces one sync.
 */
function notifyKnowledgeBase() {
  var props = PropertiesService.getScriptProperties();
  var cache = CacheService.getScriptCache();
  if (cache.get('recent')) {
    return;
  }
  cache.put('recent', '1', 20);
  Utilities.sleep(20000);

  var url = props.getProperty('KB_API_URL') + '/v1/admin/sync/sheet/' + encodeURIComponent(props.getProperty('KB_SHEET_NAME'));
  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    headers: { 'X-Admin-Token': props.getProperty('KB_ADMIN_TOKEN') },
    muteHttpExceptions: true
  });
  console.log(response.getResponseCode() + ' ' + response.getContentText());
}
