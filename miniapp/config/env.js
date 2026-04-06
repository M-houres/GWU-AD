const envMap = {
  dev: {
    // 开发期可用本机或测试机地址；发布前必须改成已备案的 HTTPS 域名
    apiBaseUrl: "http://127.0.0.1:8100/api/v1",
  },
  prod: {
    apiBaseUrl: "https://your-domain.example.com/api/v1",
  },
}

const currentEnv = "dev"

module.exports = {
  currentEnv,
  ...envMap[currentEnv],
}

