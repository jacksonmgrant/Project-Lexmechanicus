import { createBrowserRouter } from 'react-router-dom'
import { Root } from './components/Root'
import { ChatPage } from './components/pages/ChatPage'
import { UploadPage } from './components/pages/UploadPage'
import { BrowsePage } from './components/pages/BrowsePage'
import { ManagePage } from './components/pages/ManagePage'
import { BundleEditorPage } from './components/pages/BundleEditorPage'
import { AccountPage } from './components/pages/AccountPage'
import { LegalTermsPage } from './components/pages/LegalTermsPage'
import { CopyrightPolicyPage } from './components/pages/CopyrightPolicyPage'

export const router = createBrowserRouter([
    {
        path: '/',
        element: <Root />,
        children: [
            { index: true, element: <ChatPage /> },
            { path: 'upload', element: <UploadPage /> },
            { path: 'browse', element: <BrowsePage /> },
            { path: 'manage', element: <ManagePage /> },
            { path: 'manage/bundles/:bundleId', element: <BundleEditorPage /> },
            { path: 'account', element: <AccountPage /> },
            { path: 'legal/terms', element: <LegalTermsPage /> },
            { path: 'legal/copyright', element: <CopyrightPolicyPage /> },
        ],
    },
])
