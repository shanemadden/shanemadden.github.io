Title: Cleaning Up Stack Exchange's Puppet Environment
Date: 2014-01-01 00:01
Authors: Shane Madden
Category: Puppet
Tags: puppet, stackexchange
Slug: stackexchange-puppet-cleanup
Summary: Stack Exchange's Puppet environment - what we do with it and how we're improving it.

One of the first big changes I've worked on in the few months I've been at Stack Exchange has been to modernize the Puppet environment. Generally, people think of Stack Exchange as a Windows shop, and that's partly true since that's still the core of the platform, but Linux is also critical to the service we provide.  For our public-facing services, we're running Windows for the web and database servers (IIS and MSSQL), and Linux for the Redis cache nodes, HAProxy load balancers, and ElasticSearch servers.  Beyond that, we have lots of other Linux systems - Apache httpd for the blogs, mail servers for sending out post notifications and newsletters, monitoring and logging systems, and a bunch of other internal applications.

Stack Exchange has been using Puppet to manage all those Linux nodes for years, and the infrastructure was showing its age a bit.

 - Hiera was in use, but only for some of the class parameters and explicit lookups; node definitions were still just in a `site.pp` manifest.
 - The Puppet masters themselves were artisanally hand-crafted - the process of building a new master wasn't in Puppet.
 - Puppet client config was managed by just laying a static `file` resource down at `/etc/puppet/puppet.conf`, which was a set file based on the location of the system (a custom fact).

For these, the plan, respectively:

 - Move all node data to Hiera; `site.pp` should be just a `hiera_include`.
 - Make a module that builds the puppet masters.
 - Use the [inifile module](https://forge.puppetlabs.com/puppetlabs/inifile) for management of everything's `puppet.conf`.

In addition to this cleanup, we wanted to get ahead of the game in a few other areas:

 - [Configuration-file environments are deprecated](https://docs.puppetlabs.com/puppet/latest/reference/environments_classic.html#config-file-environments-are-deprecated); this makes for a good time to do something useful with directory environments - have git branches be set up as puppet environments.
 - Puppet Dashboard is not getting much love these days (since it was forked for the enterprise dashboard then handed to the community to maintain the open source version) - using [PuppetDB](https://docs.puppetlabs.com/puppetdb/latest/) for storage of that info with a frontend like [PuppetBoard](https://github.com/nedap/puppetboard) seems like the right direction to be going in.
 - [Trusted Node Data](https://docs.puppetlabs.com/puppet/3/reference/release_notes.html#new-trusted-hash-with-trusted-node-data) is.. better to use than just trusting the identity of a node as it reports it.
 - The [`$facts` hash](https://docs.puppetlabs.com/puppet/3.5/reference/release_notes.html#global-facts-hash) is the new way to get at your facts in manifests; cleaner code and no scope problems.
 - The future parser isn't quite ready for use in production, but we want to start making sure our modules are compatible.
 - [SRV records](https://docs.puppetlabs.com/guides/scaling_multiple_masters.html#option-4-dns-srv-records) are still labeled as experimental, but I've been using them in production since 3.1 and their utility far outweighs the few rough edges.

Getting From Here to There
--------------------------

That's a lot of change to implement all at once, and presents a problem: **how the hell to pull that off without breaking the nodes using Puppet?**

Our Puppet config repo lives in GitLab, with TeamCity (the same CI platform used for our software deployment) watching the master branch and, when changed, triggering a "build".  There's nothing to compile, but having a build process is still useful: it validates the syntax of the Puppet manifest files and Hiera data, and assuming that had no problems, deploys the new version to the masters.

Starting this process, there were 2 masters - one in New York, and one in our DR site in Oregon (with the two being identical aside from the NY one being the certificate authority).

In order to make all these changes in a non-disruptive way, we decided to build new master nodes in each location, get everything to where we wanted it, then migrate nodes over.

 - A new Git branch, `new_puppetmasters`, would be where all the changes would occur
 - New masters would be built - using the new module to build them, tied in to the same CA infrastructure but reporting to themselves.
 - Temporarily, the `production` environment on the new masters would point to the `new_puppetmasters` branch - after migration, this would change back to `master`
 - Nodes could then be migrated over to the new masters with a `puppet agent --test --server new_master --noop` to make sure the new environment wasn't going to blow up their applications, then dropping the `--noop` to actually move them (the new environment would have the changes to the management of `puppet.conf`, so they would stick to it once run against it once)

Having Puppet Masters Build Your Puppet Masters
-----------------------------------------------

..module structure, vagrant..


 - master module
 - branch environments (discuss why no r10k)
 - hiera
 - dashboard to puppetdb/pupeptboard
 - vagrant
 - SRV records
 - puppet client management - config 
 - teamcity builds on branches - pull script

 future - autosigning
