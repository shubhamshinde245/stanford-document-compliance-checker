"use client";

import { ToastContainer } from "react-toastify/unstyled";

export function ToastProvider() {
  return (
    <ToastContainer
      position="top-right"
      autoClose={4500}
      hideProgressBar={false}
      newestOnTop
      closeOnClick
      pauseOnHover
      draggable
      theme="light"
      limit={4}
    />
  );
}
