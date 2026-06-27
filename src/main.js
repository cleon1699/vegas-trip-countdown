import './styles.css';
import heroUrl from './assets/vegas-neon-hero.png';

const DEPARTURE = new Date('2026-08-28T13:45:00-05:00');

const app = document.querySelector('#app');

app.innerHTML = `
  <main class="page-shell" style="--hero-image: url('${heroUrl}')">
    <section class="hero" aria-labelledby="page-title">
      <div class="skyline" aria-hidden="true">
        <span class="beam beam-one"></span>
        <span class="beam beam-two"></span>
        <span class="beam beam-three"></span>
      </div>

      <div class="hero-content">
        <p class="eyebrow">Chris and Amanda to Vegas</p>
        <h1 id="page-title">The countdown is on.</h1>
        <p class="intro">
          Leaving for Las Vegas on August 28, 2026 at 1:45 PM Central Time.
        </p>

        <div class="countdown" aria-label="Countdown until departure">
          <article class="time-card">
            <span class="time-value" data-unit="days">000</span>
            <span class="time-label">Days</span>
          </article>
          <article class="time-card">
            <span class="time-value" data-unit="hours">00</span>
            <span class="time-label">Hours</span>
          </article>
          <article class="time-card">
            <span class="time-value" data-unit="minutes">00</span>
            <span class="time-label">Minutes</span>
          </article>
          <article class="time-card">
            <span class="time-value" data-unit="seconds">00</span>
            <span class="time-label">Seconds</span>
          </article>
        </div>

        <p class="status" role="status" aria-live="polite" data-status>
          Counting every second until wheels up.
        </p>
      </div>

      <aside class="trip-panel" aria-label="Trip details">
        <div class="trip-detail">
          <span class="panel-label">Departure</span>
          <strong>Friday, August 28, 2026</strong>
        </div>
        <div class="trip-detail">
          <span class="panel-label">Time</span>
          <strong>1:45 PM Central</strong>
        </div>
        <div class="trip-detail">
          <span class="panel-label">Destination</span>
          <strong>Las Vegas, Nevada</strong>
        </div>

        <section class="todo-list" aria-labelledby="todo-title">
          <div class="todo-heading">
            <span class="panel-label">Pre-trip checklist</span>
            <strong id="todo-title">Ready list</strong>
          </div>

          <label class="todo-item">
            <input type="checkbox" data-todo="book-flight">
            <span>Book flight</span>
          </label>
          <label class="todo-item">
            <input type="checkbox" data-todo="reserve-hotel-room">
            <span>Reserve hotel room</span>
          </label>
          <label class="todo-item">
            <input type="checkbox" data-todo="buy-show-tickets">
            <span>Buy show tickets</span>
          </label>
          <label class="todo-item">
            <input type="checkbox" data-todo="pick-hot-outfit">
            <span>Pick a hot outfit</span>
          </label>
          <label class="todo-item">
            <input type="checkbox" data-todo="pack-cialis-pills">
            <span>Pack the Cialis pills</span>
          </label>
        </section>
      </aside>
    </section>
  </main>
`;

const status = document.querySelector('[data-status]');
const units = {
  days: document.querySelector('[data-unit="days"]'),
  hours: document.querySelector('[data-unit="hours"]'),
  minutes: document.querySelector('[data-unit="minutes"]'),
  seconds: document.querySelector('[data-unit="seconds"]'),
};
const todoInputs = document.querySelectorAll('[data-todo]');
const defaultCheckedTodos = new Set(['book-flight', 'reserve-hotel-room']);

todoInputs.forEach((input) => {
  const savedValue = localStorage.getItem(`vegas-todo:${input.dataset.todo}`);
  input.checked =
    savedValue === null ? defaultCheckedTodos.has(input.dataset.todo) : savedValue === 'true';

  input.addEventListener('change', () => {
    localStorage.setItem(`vegas-todo:${input.dataset.todo}`, String(input.checked));
  });
});

function getCountdownParts(now = new Date()) {
  const totalMs = Math.max(0, DEPARTURE.getTime() - now.getTime());
  const totalSeconds = Math.floor(totalMs / 1000);

  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return {
    days,
    hours,
    minutes,
    seconds,
    departed: totalMs === 0,
  };
}

function updateCountdown() {
  const countdown = getCountdownParts();

  units.days.textContent = String(countdown.days).padStart(3, '0');
  units.hours.textContent = String(countdown.hours).padStart(2, '0');
  units.minutes.textContent = String(countdown.minutes).padStart(2, '0');
  units.seconds.textContent = String(countdown.seconds).padStart(2, '0');

  if (countdown.departed) {
    status.textContent = 'It is Vegas time. The trip has officially begun.';
    document.body.classList.add('has-departed');
    return;
  }

  const dayWord = countdown.days === 1 ? 'day' : 'days';
  status.textContent = `${countdown.days} ${dayWord} until takeoff-ready smiles.`;
}

updateCountdown();
setInterval(updateCountdown, 1000);

export { DEPARTURE, getCountdownParts };
