async page => {
  const names=['dof_joint1_yaw','dof_joint2_shoulder','dof_joint3_elbow','dof_joint4_wrist','dof_gripper_drive'];
  const pane=page.locator('.feature-dialog-main');
  const result=[];
  for(let i=0;i<names.length;i++){
    if((await pane.locator('.ns-dialog-title').innerText()).trim()!=='Driving mate selector')throw new Error('Wrong editor');
    const name=names[i];
    if(i>0){
      await page.locator('#assembly-tree').getByText(name,{exact:true}).click();
      await pane.getByText(name,{exact:true}).waitFor({timeout:10000});
    }
    const entry=pane.getByRole('listitem').filter({hasText:name});
    await entry.getByText('- Z',{exact:true}).click();
    if(!await entry.getByRole('checkbox').isChecked())throw new Error('Unchecked '+name);
    result.push(name);
  }
  await page.screenshot({path:'studies/low-profile-20260926/outputs/low-profile-250g/images/onshape-pose-drivers.png'});
  await pane.locator('.ns-dialog-button-ok').click();
  await pane.waitFor({state:'hidden',timeout:10000});
  return result;
}
