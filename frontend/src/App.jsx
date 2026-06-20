import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

import HotelSearch from "./components/HotelSearch";
import WeatherSearch from "./components/WeatherSearch";
import BudgetTracker from "./components/BudgetTracker";

export default function App() {
  return (
    <>
      <HotelSearch />
      <WeatherSearch />
      <BudgetTracker />
    </>
  );
}