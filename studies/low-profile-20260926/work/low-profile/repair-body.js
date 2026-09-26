async page => {
  const title = async () => (await page.locator('.ns-dialog-title').innerText()).trim();
  if (await title() !== 'camera_body') throw new Error('Wrong editor');
  const unwanted = ['CAM5_TIE_NUT_0', 'CAM5_TIE_WASHER_1', 'CAM5_TIE_BOLT_1', 'CAM5_TIE_NUT_1', 'CAM5_D405_SCREW_0', 'CAM5_D405_SCREW_1'];
  for (const name of unwanted) {
    if (await title() !== 'camera_body') throw new Error('Editor changed');
    const item = page.locator('.os-param-selection-list-entry').filter({hasText:name});
    if (await item.count() !== 1) throw new Error('Missing selection: '+name);
    await item.locator('.os-param-selection-list-entry-delete').click();
    await item.waitFor({state:'detached', timeout:10000});
  }
  for (const name of ['CAM5_D405_BODY','CAM5_D405_USB_PLUG']) {
    if (await title() !== 'camera_body') throw new Error('Editor changed');
    const part = page.locator('.os-list-item-name').filter({hasText:new RegExp('^'+name+'$')});
    if (await part.count() !== 1) throw new Error('Nonunique part: '+name);
    await part.click();
    await page.locator('.os-param-query-list-entry-text').filter({hasText:name}).waitFor({timeout:10000});
  }
  const selected = (await page.locator('.os-param-query-list-entry-text').allTextContents()).map(s=>s.trim()).sort();
  const expected = ['CAM5_D405_BODY','CAM5_D405_USB_PLUG','CAM5_D405_USB_CABLE_STUB'].sort();
  if (JSON.stringify(selected)!==JSON.stringify(expected)) throw new Error('Wrong membership: '+JSON.stringify(selected));
  await page.screenshot({path:'/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/images/onshape-camera-body-members.png'});
  await page.locator('.ns-dialog-button-ok').click();
  await page.locator('.ns-dialog-title').waitFor({state:'hidden',timeout:10000});
  return {selected, saved:true};
}
