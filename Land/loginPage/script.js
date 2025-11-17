import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import { 
  getAuth, 
  createUserWithEmailAndPassword, 
  signInWithEmailAndPassword, 
  GoogleAuthProvider, 
  signInWithPopup 
} from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

// -------------------------------------------------
// 🔥 put your firebase creds here
// -------------------------------------------------
const firebaseConfig = {
  apiKey: "AIzaSyCJYcFMThC_WrnLVv04h5RYrk-nrg3H6c8",
  authDomain: "wandermindai-6d60f.firebaseapp.com",
  projectId: "wandermindai-6d60f",
  storageBucket: "wandermindai-6d60f.firebasestorage.app",
  messagingSenderId: "402336382724",
  appId: "1:402336382724:web:5faa3b3e67b3f17198da51",
  measurementId: "G-98TQPDTBTJ"
};


// -------------------------------------------------
// init
// -------------------------------------------------
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

// -------------------------------------------------
// login with email
// -------------------------------------------------
document.getElementById("loginBtnSubmit").addEventListener("click", async(e) => {
  e.preventDefault();

  const email = document.getElementById("loginEmail").value;
  const password = document.getElementById("loginPassword").value;

  try {
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const token = await userCredential.user.getIdToken();

    localStorage.setItem("token", token);
    localStorage.setItem("username", email.split("@")[0]);

    window.location.href = "/Land/Main/index.html";
  } catch (err) {
    alert(err.message);
  }
});


// -------------------------------------------------
// register with email
// -------------------------------------------------
document.getElementById("registerBtnSubmit").addEventListener("click", async(e) => {
  e.preventDefault();

  const email = document.getElementById("registerEmail").value;
  const password = document.getElementById("registerPassword").value;

  try {
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const token = await userCredential.user.getIdToken();

    localStorage.setItem("token", token);
    localStorage.setItem("username", email.split("@")[0]);

    window.location.href = "/Land/Main/index.html";
  } catch (err) {
    alert(err.message);
  }
});


// -------------------------------------------------
// Google login
// -------------------------------------------------
document.querySelectorAll(".fa-google-plus-g").forEach(icon => {
  icon.parentElement.addEventListener("click", async(e) => {
    e.preventDefault();

    try {
      const result = await signInWithPopup(auth, googleProvider);
      const token = await result.user.getIdToken();

      const name = result.user.displayName || (result.user.email ? result.user.email.split("@")[0] : "user");

      localStorage.setItem("token", token);
      localStorage.setItem("username", name);

      window.location.href = "/Land/Main/index.html";
    } catch (err) {
      alert(err.message);
    }
  });
});
