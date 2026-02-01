const puppeteer = require('puppeteer');

(async () => {
  console.log('=== 브라우저 UI 테스트 ===\n');

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();

    // Enable console logging
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log('  [브라우저 에러]', msg.text());
      }
    });

    // 1. Go to home page
    console.log('1. 홈페이지 접속...');
    await page.goto('http://58.227.107.5:10112', { waitUntil: 'networkidle0', timeout: 30000 });
    console.log('   ✓ 페이지 로드 완료');

    // 2. Check page title
    const title = await page.title();
    console.log(`   ✓ 타이틀: ${title}`);

    // 3. Enter name
    console.log('\n2. 이름 입력...');
    await page.type('input[placeholder*="이름"]', '테스트유저');
    console.log('   ✓ 이름 입력 완료');

    // 4. Click create room button
    console.log('\n3. 방 만들기...');
    const buttons = await page.$$('button');
    for (const btn of buttons) {
      const text = await btn.evaluate(el => el.textContent);
      if (text && text.includes('만들기')) {
        await btn.click();
        console.log('   ✓ 방 만들기 버튼 클릭');
        break;
      }
    }

    // Wait for navigation
    await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 10000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 3000));

    // 5. Check current URL
    const currentUrl = page.url();
    console.log(`   ✓ 현재 URL: ${currentUrl}`);

    // 6. Take screenshot
    await page.screenshot({ path: '/tmp/room_screenshot.png', fullPage: true });
    console.log('\n4. 스크린샷 저장: /tmp/room_screenshot.png');

    // 7. Check page content
    const content = await page.evaluate(() => document.body.innerText);

    if (content.includes('연결됨') || content.includes('Connected') || content.includes('참가자')) {
      console.log('\n   ✓ 방 입장 성공!');
    }

    // Extract key info
    if (content.includes('참가자')) {
      const match = content.match(/참가자.*?(\d+)\/(\d+)/);
      if (match) {
        console.log(`   ✓ 참가자: ${match[1]}/${match[2]}`);
      }
    }

    console.log('\n=== 테스트 완료 ===');

  } catch (err) {
    console.error('에러:', err.message);
  } finally {
    await browser.close();
  }
})();
