import { resolve } from "path";

export default {
  root: ".",
  server: {
    host: "127.0.0.1",
    port: 5173,
    open: true
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        landing: resolve(__dirname, "Land/landingpage.html"),
        login: resolve(__dirname, "Land/loginPage/login.html"),
        app: resolve(__dirname, "Land/Main/index.html"),
        chat: resolve(__dirname, "Land/chat/index.html")
      }
    }
  }
};
