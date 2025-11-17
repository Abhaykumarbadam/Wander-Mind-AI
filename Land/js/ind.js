const parallax_el = document.querySelectorAll(".parallax");
let xValue = 0 , yValue = 0;
let rotateDegree = 0;

function update(cursorPos){
    parallax_el.forEach((el) => {
        let spx = el.dataset.x;
        let spy = el.dataset.y;
        let spz = el.dataset.z;
        let rotatespeed = el.dataset.rotation;


        let le = parseFloat(getComputedStyle(el).left) < window.innerWidth/2 ? 1 : -1;
        let zValue = (cursorPos - parseFloat(getComputedStyle(el).left)) * le *0.1;
        console.log(zValue);

        el.style.transform = `perspective(2300px) translateZ(${zValue * spz}px)
        rotateY(${rotateDegree * rotatespeed}deg)
        translateX(calc(-50% + ${-xValue*(spx)}px)) 
        translateY(calc(-50% + ${yValue*spy}px)) `;
    });
}

update(0);

window.addEventListener("mousemove", (e) => {
    xValue = e.clientX - window.innerWidth / 2;
    yValue = e.clientY - window.innerHeight / 2;

    rotateDegree = (xValue / (window.innerWidth / 2)) * 20;

    update(e.clientX);
});

