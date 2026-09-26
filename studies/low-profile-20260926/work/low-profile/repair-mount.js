async page => {
  const missing = ['CAM5_TIE_NUT_0','CAM5_TIE_WASHER_1','CAM5_TIE_BOLT_1','CAM5_TIE_NUT_1','CAM5_D405_SCREW_0','CAM5_D405_SCREW_1'];
  for (const name of missing) {
    const state=await page.evaluate(n=>({title:document.querySelector('.ns-dialog-title')?.textContent.trim(),count:[...document.querySelectorAll('.os-list-item-name')].filter(e=>e.textContent.trim()===n).length}),name);
    if(state.title!=='camera_mount'||state.count!==1)throw new Error(JSON.stringify(state));
    await page.locator('.os-list-item-name').filter({hasText:new RegExp('^'+name+'$')}).click();
    await page.waitForFunction(n=>[...document.querySelectorAll('.os-param-query-list-entry-text')].some(e=>e.textContent.trim()===n),name,{timeout:10000});
  }
  const selected=(await page.locator('.os-param-query-list-entry-text').allTextContents()).map(s=>s.trim());
  if(selected.length!==10||!selected.includes('CAM5_BASE')||selected.some(n=>['CAM5_D405_BODY','CAM5_D405_USB_PLUG','CAM5_D405_USB_CABLE_STUB'].includes(n)))throw new Error('Unexpected membership: '+JSON.stringify(selected));
  await page.screenshot({path:'/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/images/onshape-camera-mount-members.png'});
  await page.locator('.ns-dialog-button-ok').click();
  await page.locator('.ns-dialog-title').waitFor({state:'hidden',timeout:10000});
  return {selected,saved:true,union_note:'CAM5_BASE entry retains the unchanged base plus 8 fasteners; verify exported actual group count'};
}
