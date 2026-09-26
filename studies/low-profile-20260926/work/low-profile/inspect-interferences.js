async page => {
  const pane=page.locator('.feature-dialog-main');
  const rows=pane.locator('.os-param-query-list-entry-text').filter({hasText:' and '});
  if(await rows.count()!==6)throw new Error('Unexpected interference count');
  await page.mouse.move(1100,350);await page.mouse.wheel(0,-400);await page.waitForTimeout(1000);
  const results=[];
  for(let i=0;i<6;i++){
    const row=rows.nth(i);
    await row.click();await row.hover();await page.waitForTimeout(1000);
    results.push({index:i,pair:(await row.innerText()).trim(),displayed_box:await row.locator('..').getAttribute('data-bs-original-title')});
    await page.screenshot({path:'/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/images/onshape-interference-mid-'+i+'.png'});
  }
  return {pose:'restored_mid',selected_instances:12,include_standard_content:false,show_top_level_only:false,results};
}
