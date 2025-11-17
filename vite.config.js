import { resolve } from "path";

export default {
  root: ".",
  server: {
    host: "127.0.0.1",
    port: 5173,
    open: "/Land/loginPage/login.html"
  },
  build: {
    rollupOptions: {
      input: {
        login: resolve(__dirname, "Land/loginPage/login.html"),
        main: resolve(__dirname, "Land/Main/index.html")
      }
    }
  }
};
