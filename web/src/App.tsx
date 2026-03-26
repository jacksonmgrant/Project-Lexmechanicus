import React from 'react'
import { RouterProvider } from 'react-router-dom'
import { Meta } from './seo/Meta'
import { router } from './routes'
import { AppProvider } from './context/AppContext'

export default function App() {
    return (
        <AppProvider>
            <Meta />
            <RouterProvider router={router} />
        </AppProvider>
    )
}
