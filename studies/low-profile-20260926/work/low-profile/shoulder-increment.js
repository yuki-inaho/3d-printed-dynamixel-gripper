async page => {
  const id='y64CuidZMOY3IiA8';
  const cell=page.locator('.os-tr[data-id="'+id+'"] .os-td').filter({has:page.locator('[data-parameter-id=namedPositionParameterValue]')});
  const angle=page.locator('.os-tr[data-id="'+id+'"] .os-td').filter({has:page.locator('input.os-param-number')}).nth(1);
  const result=[];
  for(let deg=4;deg<=10;deg++){
    const name=deg===10?'small_joint2_shoulder':'shoulder_waypoint_'+deg;
    await cell.dblclick();await cell.locator('input').fill(name);await cell.locator('input').press('Enter');
    await page.waitForTimeout(2000);
    if(await cell.locator('input').inputValue()!==name)throw new Error('Name not saved');
    await angle.dblclick();await angle.locator('input').fill(deg+' deg');await angle.locator('input').press('Enter');
    await page.waitForTimeout(2000);
    if(parseFloat(await angle.locator('input').inputValue())!==deg)throw new Error('Angle not saved');
    await cell.click({button:'right'});await page.getByText('Apply named position',{exact:true}).click();
    await page.waitForFunction(n=>document.body.innerText.includes(n+' is applied.')||document.body.innerText.includes(n+' could not'),name,{timeout:20000});
    const body=await page.locator('body').innerText();
    if(body.includes(name+' could not'))throw new Error('Solver failed at '+deg);
    await page.waitForTimeout(2000);
    result.push({deg,applied:true});
  }
  await page.screenshot({path:'studies/low-profile-20260926/outputs/low-profile-250g/images/onshape-pose-small_joint2_shoulder.png'});
  return {steps:result,stored:await page.locator('.os-tr[data-id="'+id+'"] input.os-param-number').evaluateAll(es=>es.map(e=>e.value))};
}
