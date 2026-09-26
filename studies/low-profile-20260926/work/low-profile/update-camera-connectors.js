async page => {
  const result=[];
  for (const suffix of ['a','b']) {
    const name='mc_camera_body_fixed_'+suffix;
    if(suffix==='b') await page.getByText(name,{exact:true}).dblclick();
    if((await page.locator('.ns-dialog-title').innerText()).trim()!==name)throw new Error('Wrong editor');
    const y=page.locator('[data-parameter-id="translationY"] input');
    const z=page.locator('[data-parameter-id="translationZ"] input');
    await y.fill('165 mm'); await y.press('Tab');
    await z.fill('235 mm'); await z.press('Tab');
    result.push({name,y:await y.inputValue(),z:await z.inputValue()});
    await page.screenshot({path:'/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/images/onshape-camera-connector-'+suffix+'.png'});
    await page.locator('.ns-dialog-button-ok').click();
    await page.locator('.ns-dialog-title').waitFor({state:'hidden',timeout:10000});
  }
  await page.getByRole('textbox',{name:'Filter by name or type',exact:true}).fill('');
  return result;
}
