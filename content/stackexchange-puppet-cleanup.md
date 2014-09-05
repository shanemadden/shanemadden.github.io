Title: Cleaning Up Stack Exchange's Puppet Environment
Date: 2014-01-01 00:01
Authors: Shane Madden
Category: Puppet
Tags: puppet, stackexchange
Slug: stackexchange-puppet-cleanup

One of the first big changes I've worked on in the few months I've been at Stack Exchange has been to modernize the Puppet environment. People think of Stack Exchange as a Windows shop, and that's partly true since Windows is still the core of the platform, but Linux is also critical to the service we provide. For our public-facing services, we're running Windows for the web and database servers (IIS and MSSQL), and Linux for the Redis cache nodes, HAProxy load balancers, and ElasticSearch servers.  Beyond that, we have lots of other Linux systems - Apache httpd for the blogs, mail servers for sending out post notifications and newsletters, monitoring and logging systems, and a bunch of other internal applications.

Stack Exchange has been using Puppet to manage all those Linux nodes for years, and the infrastructure was showing its age a bit.

 - Hiera was in use, but only for some of the class parameters and explicit lookups from some modules; node definitions were still just in a `site.pp` manifest.
 - The Puppet masters themselves were artisanally hand-crafted - the process of building a new master wasn't in Puppet.
 - Puppet client config was managed by just laying a static `file` resource down at `/etc/puppet/puppet.conf`, which was a set file based on the location of the system (a custom fact, parsed from the system's hostname).

For these, the plan, respectively:

 - Move all node data to Hiera; `site.pp` should be just a `hiera_include`.
 - Make a module that builds the puppet masters reproducibly.
 - Use the [inifile module](https://forge.puppetlabs.com/puppetlabs/inifile) for management of everything's `puppet.conf`

In addition to this cleanup, we wanted to get ahead of the game in a few other areas:

 - [Configuration-file environments are deprecated](https://docs.puppetlabs.com/puppet/latest/reference/environments_classic.html#config-file-environments-are-deprecated); this makes for a good time to do something useful with directory environments - have git branches be set up as puppet environments.
 - Puppet Dashboard is not getting much love these days (since it was forked for the enterprise dashboard then handed to the community to maintain the open source version) - using [PuppetDB](https://docs.puppetlabs.com/puppetdb/latest/) for storage of that info with a frontend like [PuppetBoard](https://github.com/nedap/puppetboard) seems like the right direction to be going in.
 - [Trusted node data](https://docs.puppetlabs.com/puppet/3/reference/release_notes.html#new-trusted-hash-with-trusted-node-data) is.. better to use than just trusting the identity of a node as it reports it.
 - The [`$facts` hash](https://docs.puppetlabs.com/puppet/3.5/reference/release_notes.html#global-facts-hash) is the new way to get at your facts in manifests; cleaner code and no scope problems.
 - The future parser isn't quite ready for use in production, but we want to start making sure our modules are compatible.
 - [SRV records](https://docs.puppetlabs.com/guides/scaling_multiple_masters.html#option-4-dns-srv-records) are still labeled as experimental, but I've been using them in production since 3.1 and their utility far outweighs the few rough edges (automatic load balancing, and failover with priority order, for your clients to connect to your masters!)

Getting From Here to There
--------------------------

That's a lot of change to implement all at once, and presents a problem: **how the hell to pull that off without breaking the nodes using Puppet?**

Our Puppet config repo lives in GitLab, with TeamCity (the same CI platform used for our software deployment) watching the master branch and, when changed, triggering a "build".  There's nothing to compile, but having a build process is still useful: it validates the syntax of the Puppet manifest files and Hiera data, and assuming that had no problems, deploys the new version to the masters.

Starting this process, there were 2 masters - one in New York, and one in our DR site in Oregon (with the two being identical aside from the NY one being the certificate authority).

In order to make all these changes in a non-disruptive way, we decided to build new master nodes in each location, get everything to where we wanted it, then migrate nodes over.

 - A new Git branch, `new_puppetmasters`, would be where all the changes would occur - and make TeamCity trigger deployments on changes to either branch.
 - New masters would be built - using the new module to build them, tied in to the same CA infrastructure but reporting to themselves
 - Temporarily, the `production` environment on the new masters would point to the `new_puppetmasters` branch (so that nodes reporting to them would get the new stuff) - after migration, this would change back to `master`
 - Nodes could then be migrated over to the new masters with a `puppet agent --test --server new_master --noop` to make sure the new environment wasn't going to blow up their applications, then dropping the `--noop` to actually move them (the new environment would have the changes to the management of `puppet.conf`, so they would stick to it once run against it once)

Having Puppet Masters Build Your Puppet Masters
-----------------------------------------------

*yo dawg?*

The configuration of Puppet itself now happens with two modules; puppet_client (applied globally to all systems) and puppet_master (applied to the masters).  Previously, there was a class in a "shared local stuff" module, 'site', that was dropping a static `puppet.conf`, which would vary based on a couple parameters - location and whether the node was a puppet master or not.

With the new structure, the client module has `inifile` resources for settings in `puppet.conf` that all nodes get (`server` and `environment` set to parameter values from Hiera, and some static stuff like `stringify_facts = false` and `ordering = random`; [manifest ordering](http://puppetlabs.com/blog/introducing-manifest-ordered-resources) is nice, but we'd like to have the dependencies spelled out so something doesn't bite us when we move resources around in a class - and this keeps us honest on those resource relationships), and the master module has resources for settings that only masters care about (`ca` to true or false based on Hiera data, static stuff like `trusted_node_data = true`, and `dns_alt_names` set to a bunch of combinations of hostnames and domains that might be used to hit the master).

The `puppet_client` module is also responsible for the agent service and setting the puppet-related packages (`hiera`, `facter`, `augeas`) to the desired versions - with the version being from Hiera data so we can make sure the masters upgrade to new versions of Puppet before the rest of the nodes.

The `puppet_master` module also gets to do a bunch of other setup..

 - Installs all that's needed to [run the master service under Apache with Passenger](https://docs.puppetlabs.com/guides/passenger.html) and manages the Apache config and service for that
 - Configures an authorized SSH key so the TeamCity agents can log in and deploy new versions (and new branches)
 - On the master that's a CA, runs a daily backup of the `/var/lib/puppet/ssl/ca` directory to a tgz archive, rsyncs those archives to the other master(s); on the non-CA master(s), restores the most recent archive into `/var/lib/puppet/ssl/ca` daily (so that they're reasonably ready to be the CA if our [primary data center were to drift out to sea](http://status.fogcreek.com/2012/10/services-still-on-backup-power-diesel-bucket-brigade-continues.html))

With all of that handled in Puppet, not only do we get the benefit of a master being built the same way every time, but we can let them get built automatically, which is a great help for..

### Vagrant ###

For testing Puppet modules, we have a Vagrant environment that gives us a master node (build with the same module as the production nodes) and client devices - one by default more if needed.  When starting up the vagrant environment, the first system gets built with the [`puppet apply` provisioner](https://docs.vagrantup.com/v2/provisioning/puppet_apply.html); subsequent systems get built with the [`puppet agent` provisioner](https://docs.vagrantup.com/v2/provisioning/puppet_agent.html), getting their configuration from the master node that was just built.

The vagrant systems have a special fact (`puppet.facter = {"vagrant" => "puppet"}` in the Vagrantfile, then a `file` resource persisting that to `/etc/facter/facts.d`) which flags them as being built by vagrant; this gives these some Vagrant-specific config from Hiera, setting an `insecure` parameter for the `puppet_master` class.  We use this to light up autosigning, so the Vagrant boxes built after the first will get a certificate:

    ini_setting { 'puppet_autosign':
      setting => 'autosign',
      value   => $insecure,
      path    => '/etc/puppet/puppet.conf',
      section => 'main',
    }

The only other thing that's *special* about what we do through Vagrant is that we want to make sure the Hiera lookups succeed for the built systems regardless of what DNS suffix they have (since we have remote workers, and people's home networks vary):

    :hierarchy:
      - "host/%{::certname_trusted}"
      - "host/%{::hostname}"

(that `certname_trusted` variable doesn't make sense without context from our `site.pp`...)

    # workaround until the $trusted hash can be used in hiera.. (https://tickets.puppetlabs.com/browse/HI-14)
    $certname_trusted = $trusted['certname']

(...using this to generate a node's catalog is much better than the node's self-reported `fqdn` fact, which can differ from the hostname in the client certificate that was used to authenticate to the puppet master)

Other than those couple bits of special casing, the Vagrant systems are built by Puppet identically to our production systems - this gives us a high degree of confidence that the testing we do under Vagrant won't have extra surprises when deployed to production.

Speaking of Hiera..
-------------------

`site.pp`, or more specifically, having more than a couple lines in `site.pp`, is my enemy.  Classic node definitions in manifests required either inheritance, regex node names, or making the same change in multiple places, to manage multiple nodes with effectively the same role.  `hiera_include()`, plus Hiera's automatic data bindings for class parameters, is a much healthier pattern for fetching configuration data - and for the cases where those don't quite cover the needs of a node definition, all that's needed is a little helper manifest.

(added role tier, show example)


 X master module
 - branch environments (discuss why no r10k)
 - hiera
 - dashboard to puppetdb/pupeptboard - discuss HA, link to jira epic
 X vagrant
 - SRV records
 X puppet client management - config 
 - teamcity builds on branches - pull script
 - merge requests
 - talk about ordering

 future - autosigning, module_data?
