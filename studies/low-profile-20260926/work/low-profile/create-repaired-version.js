async page => {
  await page.locator('[data-bs-original-title="Create version…"],[title="Create version…"],[aria-label="Create version…"]').click();
  const d=page.getByRole('dialog');
  await d.getByPlaceholder('Name',{exact:true}).fill('V2 Low profile D405 - corrected jaw pads');
  await d.getByPlaceholder('Description',{exact:true}).fill('30 deg D405, +20 mm fingers. Corrected PG3_pad_L/R composite membership after independent STEP motion check exposed opposite-jaw tracking in V1. 11 UI STEP poses exported for fresh numerical verification. Physical strength, material and durability remain unverified.');
  await page.screenshot({path:'/home/inaho-omen/Documents/Codex/2026-09-26/onshape/outputs/low-profile-250g/images/onshape-create-version-v2.png'});
  await d.getByRole('button',{name:'Create',exact:true}).click();
  await d.waitFor({state:'hidden',timeout:30000});
  return {created:true,url:page.url()};
}
