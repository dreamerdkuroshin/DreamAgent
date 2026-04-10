// Import required modules
import { ScrollReveal } from './scrollReveal.js';

// Define constants
const sections = ['hero', 'portfolio', 'about', 'contact', 'footer'];
const colors = ['#3498db', '#2ecc71', '#f1c40f'];

// Initialize ScrollReveal
ScrollReveal().reveal('.scroll-reveal');

// Add event listener to nav links
document.querySelectorAll('.nav-link').forEach((link) => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const sectionId = link.getAttribute('href').split('#')[1];
    const section = document.getElementById(sectionId);
    section.scrollIntoView({ behavior: 'smooth' });
  });
});

// Add event listener to portfolio items
document.querySelectorAll('.portfolio-item').forEach((item) => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const modalId = item.getAttribute('data-modal-id');
    const modal = document.getElementById(modalId);
    modal.classList.add('show');
    document.body.classList.add('modal-open');
  });
});

// Add event listener to modal close buttons
document.querySelectorAll('.modal-close').forEach((button) => {
  button.addEventListener('click', (e) => {
    e.preventDefault();
    const modal = button.parentNode.parentNode;
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
  });
});

// Add event listener to contact form submit button
document.querySelector('.contact-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  const name = formData.get('name');
  const email = formData.get('email');
  const message = formData.get('message');
  // Send data to server or database
  console.log(name, email, message);
});

// Initialize PostgreSQL database connection
// const { Pool } = require('pg');
// const pool = new Pool({
//   user: 'username',
//   host: 'localhost',
//   database: 'database',
//   password: 'password',
//   port: 5432,
// });

// Initialize Admin Dashboard
// const adminDashboard = require('./adminDashboard.js');
// adminDashboard.init();