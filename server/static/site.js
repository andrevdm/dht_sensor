function formatTime(a){
  if(!a || a <= 5000){
    return '';
  }

  return luxon.DateTime.fromMillis(a).toFormat("yyyy/LL/dd HH:mm:ss");
}

function formatBytes(a){
  if(!a){
    return '';
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let i = 0;
  while(a > 1024){
    a /= 1024;
    i++;
  }

  return i == 0 ? `${a}B` : `${a.toFixed(2)} ${units[i]}`;
}


function stripEscapeSequences(s){
  if(!s){
    return '';
  }

  return s.replace(/\u001b\[.*?m/g, '');
}
