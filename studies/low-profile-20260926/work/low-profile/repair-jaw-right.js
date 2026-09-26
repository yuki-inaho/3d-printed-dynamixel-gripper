async page => {
  const group='jaw_r';
  const names=['PG3_carriage_R','PG3_finger_R','PG3_pad_R','PG3_pivot_carriage_R_washer','PG3_pivot_carriage_R_bolt','PG3_pivot_carriage_R_nut','PG3_finger_R_-14_washer','PG3_finger_R_-14_bolt','PG3_finger_R_-14_nut','PG3_finger_R_14_washer','PG3_finger_R_14_bolt','PG3_finger_R_14_nut'];
  for(const name of names){
    if((await page.locator('.ns-dialog-title').innerText()).trim()!==group)throw Error('wrong editor');
    const part=page.locator('.os-list-item-name').filter({hasText:new RegExp('^'+name+'$')});
    if(await part.count()!==1)throw Error('nonunique/missing '+name);
    await part.click();
    await page.locator('.os-param-query-list-entry-text').filter({hasText:new RegExp('^\\s*'+name+'\\s*$')}).waitFor({timeout:20000});
  }
  const selected=(await page.locator('.os-param-query-list-entry-text').allTextContents()).map(x=>x.trim()).sort();
  if(JSON.stringify(selected)!==JSON.stringify(names.sort()))throw Error('membership mismatch');
  await page.screenshot({path:'studies/low-profile-20260926/outputs/low-profile-250g/images/onshape-jaw-right-repaired.png'});
  await page.locator('.ns-dialog-button-ok').click();
  await page.locator('.ns-dialog-title').waitFor({state:'hidden',timeout:20000});
  return {group,selected,saved:true};
}
