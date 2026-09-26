async page => {
  const target=__CASE__;
  const rows=await page.locator('[data-parameter-id=namedPositionParameterValue] input').evaluateAll(es=>es.map(e=>({name:e.value,id:e.closest('.os-tr').getAttribute('data-id')})));
  const row=rows.find(r=>r.name===target.name);
  const zero=rows.find(r=>r.name==='zero');
  if(!row||!zero)throw new Error('Expected existing target and zero');
  const cell=id=>page.locator('.os-tr[data-id="'+id+'"] .os-td').filter({has:page.locator('[data-parameter-id=namedPositionParameterValue]')});
  const settle=()=>page.waitForTimeout(2000);
  const apply=async(id,name)=>{
    await cell(id).click({button:'right'});
    await page.getByText('Edit named position',{exact:true}).waitFor();
    const action=page.getByText('Apply named position',{exact:true});
    if(!await action.isVisible()){await page.keyboard.press('Escape');return 'already current';}
    await action.click();
    await page.waitForFunction(n=>document.body.innerText.includes(n+' is applied.')||document.body.innerText.includes(n+' could not'),name,{timeout:20000});
    if((await page.locator('body').innerText()).includes(name+' could not'))throw new Error('Solver failed: '+name);
    await settle();return 'applied message';
  };
  await apply(zero.id,'zero');
  const angle=page.locator('.os-tr[data-id="'+row.id+'"] .os-td').filter({has:page.locator('input.os-param-number')}).nth(target.col);
  const steps=[];
  const n=Math.ceil(Math.abs(target.deg)/target.increment);
  for(let i=1;i<=n;i++){
    const deg=i===n?target.deg:Math.sign(target.deg)*i*target.increment;
    const name=i===n?target.name:target.name+'_waypoint_'+i;
    await cell(row.id).dblclick();await cell(row.id).locator('input').fill(name);await cell(row.id).locator('input').press('Enter');await settle();
    if(await cell(row.id).locator('input').inputValue()!==name)throw new Error('Name not persisted');
    await angle.dblclick();await angle.locator('input').fill(deg+' deg');await angle.locator('input').press('Enter');await settle();
    const vals=await page.locator('.os-tr[data-id="'+row.id+'"] input.os-param-number').evaluateAll(es=>es.map(e=>parseFloat(e.value)));
    if(vals.some((v,j)=>Math.abs(v-(j===target.col?deg:0))>1e-8))throw new Error('Values not persisted '+JSON.stringify(vals));
    steps.push({deg,evidence:await apply(row.id,name)});
  }
  await page.screenshot({path:'studies/low-profile-20260926/outputs/low-profile-250g/images/onshape-pose-'+target.name+'.png'});
  return {name:target.name,rowId:row.id,stored_deg:await page.locator('.os-tr[data-id="'+row.id+'"] input.os-param-number').evaluateAll(es=>es.map(e=>parseFloat(e.value))),applied_message:true,steps,numerical_geometry_check:'pending UI STEP export'};
}
