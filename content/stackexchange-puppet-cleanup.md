Title: Cleaning Up Stack Exchange's Puppet Environment
Date: 2014-01-01 00:01
Authors: Shane Madden
Category: Puppet
Tags: puppet, stackexchange
Slug: stackexchange-puppet-cleanup
Summary: Stack Exchange's Puppet environment - what we do with it and how we're improving it.

One of the first big changes I've worked on in the few months I've been at Stack Exchange has been to modernize the Puppet environment. Generally, people think of Stack Exchange as a Windows shop, and that's kinda true, but we have a lot of Linux in the mix as well.  For our public-facing services, we're running Windows for the web and database servers (IIS and MSSQL), and Linux for the Redis cache nodes, HAProxy load balancers, and ElasticSearch servers.  Beyond that, we have lots of other Linux systems - Apache httpd for the blogs, mail servers for sending out post notifications and newsletters, monitoring and logging systems, and a bunch of other internal applications.

Stack Exchange has been using Puppet to manage all those Linux nodes for years, and the infrastructure was showing its age a bit.

 - Hiera was in use, but only for class parameters and explicit lookups; node definitions were still just in a `site.pp` manifest.
 - The puppet masters themselves were artisanally hand-crafted - the process of building a new master wasn't in Puppet.
 - Puppet client config was managed by just laying a static `file` resource down at `/etc/puppet/puppet.conf`, which was a set file based on the location of the system.

So, in addition to cleaning up those things, we wanted to get ahead of the game in a few other areas:

 - Configuration-file environments are deprecated; this makes for a good time to do something useful with directory environments.
 - Puppet Dashboard is not getting much love these days (since it was forked for the enterprise dashboard then handed to the community to maintain the open source version) - using [PuppetDB](https://docs.puppetlabs.com/puppetdb/latest/) for storage of that info with a frontend like [PuppetBoard](https://github.com/nedap/puppetboard) seems like the right direction to be going in.
 - Trusted Node Data, the `$facts` hash, and the future parser
 


 - master module
 - branch environments (discuss why no r10k)
 - hiera
 - dashboard to puppetdb/pupeptboard
 - vagrant
 - SRV records
 - puppet client management - config

 future - autosigning
