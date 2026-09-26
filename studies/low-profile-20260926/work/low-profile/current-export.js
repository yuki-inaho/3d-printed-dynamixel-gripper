async page => {
  const d=page.getByRole('dialog');
  await d.getByRole('textbox').first().fill('low-profile-V2-final');
  await d.locator('#export-format-dropdown').selectOption({label:'STEP'});
  await d.locator('#step-parasolid-preprocessing-on-read').selectOption({label:'None'});
  await d.getByRole('checkbox',{name:'Export models oriented Y axis up',exact:true}).uncheck();
  await d.getByRole('checkbox',{name:'Use latest version',exact:true}).uncheck();
  await d.locator('#step-export-version-dropdown').selectOption({label:'AP242'});
  await d.getByRole('checkbox',{name:'Use custom units for export',exact:true}).check();
  const units=d.getByRole('combobox').filter({has:page.getByRole('option',{name:'Millimeter',exact:true})});
  await units.selectOption({label:'Millimeter'});
  await d.getByRole('checkbox',{name:'Export unique parts as individual files',exact:true}).uncheck();
  await d.getByRole('checkbox',{name:'Include hidden instances in export',exact:true}).check();
  const settings=await d.getByRole('combobox').evaluateAll(es=>es.map(e=>({id:e.id,selected:e.selectedOptions[0]?.textContent})));
  await page.screenshot({path:'/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/images/onshape-step-export-v2.png'});
  const pending=page.waitForEvent('download',{timeout:180000});
  await d.getByRole('button',{name:'Export',exact:true}).click();
  const download=await pending;
  const suggested=download.suggestedFilename();
  const ext=suggested.split('.').pop().toLowerCase();
  if(!['step','stp','zip'].includes(ext))throw new Error('Unexpected download '+suggested);
  const path='/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/CAD/native-poses/zero.'+ext;
  await download.saveAs(path);
  return {pose:"version_zero",source_url:page.url(),settings,suggested,path,error:await download.failure()};
}
