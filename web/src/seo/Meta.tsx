import React from 'react'
import { Helmet } from 'react-helmet-async'
export const Meta: React.FC = () => (
    <Helmet>
        <link rel="canonical" href={location.href} />
        <script type="application/ld+json">{JSON.stringify({
            '@context': 'https://schema.org', '@type': 'WebApplication',
            name: 'Rules Lookup', applicationCategory: 'Game',
            description: 'Mobile-first rules and FAQ search on your uploaded packs.'
        })}</script>
    </Helmet>
)