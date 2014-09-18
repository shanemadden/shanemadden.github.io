Title: Cleaning Up Stack Exchange's Puppet Environment
Date: 2014-01-01 00:01
Authors: Shane Madden
Category: Puppet
Tags: puppet, stackexchange
Slug: stackexchange-puppet-cleanup

One of the first big changes I've worked on in the few months I've been at Stack Exchange has been to modernize the Puppet environment. People think of Stack Exchange as a Windows shop, and that's partly true since Windows is still the core of the platform, but Linux is also critical to the service we provide. For our public-facing services, we're running Windows for the web and database servers (IIS and MSSQL), and Linux for the Redis cache nodes, HAProxy load balancers, and ElasticSearch servers.  Beyond that, we have lots of other Linux systems - Apache httpd for the blogs, mail servers for sending out post notifications and newsletters, monitoring and logging systems, and a bunch of other internal applications.

Stack Exchange has been using Puppet to manage all those Linux nodes for years, and the infrastructure and configuration logic was showing its age a bit.

 - Hiera was in use, but only for some of the class parameters and explicit lookups from some modules; node definitions were still just in a `site.pp` manifest.
 - The Puppet masters themselves were artisanally hand-crafted - the process of building a new master wasn't in Puppet.
 - Puppet client config was managed by just laying a static `file` resource down at `/etc/puppet/puppet.conf`, which was a set file based on the location of the system (a custom fact, parsed from the system's hostname).

For these, the plan, respectively:

 - Move all node data to Hiera; `site.pp` should be just a `hiera_include`.  Get all the sensitive data bits into files managed by [BlackBox](https://github.com/StackExchange/blackbox), so that we're not walking around with passwords in every laptop that clones the git repo.
 - Make a module that builds the puppet masters reproducibly.
 - Use the [inifile module](https://forge.puppetlabs.com/puppetlabs/inifile) for management of everything's `puppet.conf`

In addition to this cleanup, we wanted to get ahead of the game in a few other areas:

 - [Configuration-file environments are deprecated](https://docs.puppetlabs.com/puppet/latest/reference/environments_classic.html#config-file-environments-are-deprecated); this makes for a good time to do something useful with directory environments - have git branches be set up as puppet environments.
 - Puppet Dashboard is not getting much love these days (since it was forked for the enterprise dashboard then handed to the community to maintain the open source version) - using [PuppetDB](https://docs.puppetlabs.com/puppetdb/latest/) for storage of that info with a frontend like [PuppetBoard](https://github.com/nedap/puppetboard) seems like the right direction to be going in.
 - [Trusted node data](https://docs.puppetlabs.com/puppet/3/reference/release_notes.html#new-trusted-hash-with-trusted-node-data) is.. better to use than just trusting the identity of a node as it reports it; using the `clientcert` fact to determine a node's catalog via Hiera gives authenticated nodes the ability to masquerade as other nodes, which can be a security problem in some environments (like ours).
 - The [`$facts` hash](https://docs.puppetlabs.com/puppet/3.5/reference/release_notes.html#global-facts-hash) is the new way to get at your facts in manifests; cleaner code and no scope problems.
 - The future parser isn't quite ready for use in production, but it's close; we want to start making sure our modules are compatible.
 - [SRV records](https://docs.puppetlabs.com/guides/scaling_multiple_masters.html#option-4-dns-srv-records) are still labeled as experimental, but I've been using them in production since 3.1 and their utility far outweighs the few rough edges (automatic load balancing, and failover with priority order, for your clients to connect to your masters!)

Getting From Here to There
--------------------------

That's a lot of change to implement all at once, and presents a problem: **how the hell to pull that off without breaking the nodes using Puppet?**

Our Puppet config repo lives in GitLab, with TeamCity (the same CI platform used for our software deployment) watching the master branch and, when changed, triggering a "build".  There's nothing to compile, but having a build process is still useful: it validates the syntax of the Puppet manifest files and Hiera data, and assuming that had no problems, deploys the new version to the masters, then tells us when it's done in chat so we can use the new configs as soon as they're in place.

Starting this process, there were 2 masters - one in New York, and one in our DR site in Oregon (with the two being identical aside from the NY one being the certificate authority).

In order to make all these changes in a non-disruptive way, we decided to build new master nodes in each location, get everything to where we wanted it, then migrate nodes over.

 - A new Git branch, `new_puppetmasters`, would be where all the changes would occur - and make TeamCity trigger deployments on changes to either branch.
 - New masters would be built - using the new module to build them, tied in to the existing Puppet CA infrastructure but reporting to themselves
 - Temporarily, the `production` environment on the new masters would point to the `new_puppetmasters` branch (so that nodes reporting to them would get the new stuff) - after migration, this would change back to `master`
 - Nodes could then be migrated over to the new masters with a `puppet agent --test --server new_master --noop` to make sure the new environment wasn't going to blow up their applications, then dropping the `--noop` to actually move them (the new environment would have the changes to the management of `puppet.conf`, so they would stick to it once run against it once)

Having Puppet Masters Build Your Puppet Masters
-----------------------------------------------

*yo dawg?*

The configuration of Puppet itself now happens with two modules; puppet_client (applied globally to all systems) and puppet_master (applied to the masters).  Previously, there was a class in a "shared local stuff" module, 'site', that was dropping a static `puppet.conf`, which would be a different static file based on a couple parameters - node location and whether the node was a puppet master or not.

With the new structure, the client module has `inifile` resources for settings in `puppet.conf` that all nodes get (`server` and `environment` set to parameter values from Hiera, and some static stuff like `stringify_facts = false` and `ordering = random`; [manifest ordering](http://puppetlabs.com/blog/introducing-manifest-ordered-resources) is nice, but we'd like to have the dependencies spelled out so something doesn't bite us when we move resources around in a class - and this keeps us honest on those resource relationships), and the master module has resources for settings that only masters care about (`ca` to true or false based on Hiera data, static stuff like `trusted_node_data = true`, and `dns_alt_names` set to a bunch of combinations of hostnames and domains that might be used to hit the master).

The `puppet_client` module is also responsible for the agent service and setting the puppet-related packages (`hiera`, `facter`, `augeas`) to the desired versions - with the version being from Hiera data so we can make sure the masters upgrade to new versions of Puppet before the rest of the nodes.

The `puppet_master` module also gets to do a bunch of other setup..

 - Installs all that's needed to [run the master service under Apache with Passenger](https://docs.puppetlabs.com/guides/passenger.html) and manages the Apache config and service for that
 - Configures an authorized SSH key so the TeamCity agents can log in via SSH to deploy new versions (and new branches)
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

`site.pp`, or more specifically, having more than a couple lines in `site.pp`, is my enemy.  Classic node definitions in manifests required either inheritance (now [deprecated](https://docs.puppetlabs.com/puppet/latest/reference/deprecated_language.html#node-inheritance)), regex node names, or making the same change in multiple places, to manage multiple nodes with effectively the same role.  `hiera_include()`, plus Hiera's automatic data bindings for class parameters, is a much healthier pattern for fetching configuration data - and for the cases where those don't quite cover the needs of a node definition, all that's needed is a little helper manifest (say, for taking a passed-in array or hash table and making a bunch of instances of a defined type from it).

We looked at, but didn't use, the [roles and profiles pattern](http://garylarizza.com/blog/2014/02/17/puppet-workflow-part-2/) - we're comfortable with just letting Hiera data bindings handle this kind of thing, and lets us define a machine role with pure Hiera, no manifests.

So, what this looks like, is..

 - In `site.pp`, there's a Hiera lookup for a machine's role before calling `hiera_include()`:

       $role = hiera('role', undef)
       hiera_include('classes')

   ..which is its own tier in `hiera.yaml`..

       :hierarchy:
         - "host/%{::certname_trusted}"
         - "host/%{::hostname}"
         - "role/%{::role}"

 - A node sets its role (and in most cases nothing else, unless there's some node-specific config as there is here since not all masters are CAs) in its Hiera file:

       {
         "puppet_master::ca_master": true,
         "role": "puppet_master"
       }

   ..and the role file does the rest..

       {
         "classes": [
           "puppet_master",
           "puppetdb::master::config"
         ],
         "puppet_master::secret_setup": true
       }

 - And in cases where it's needed, the role file can call a helper class to do anything that needs to happen in a manifest:

       {
         "classes": [
           "role::redis_primary",
           "redis"
         ],
         "redis::user": "redis"
       }

   ..which is just a simple class to cover the gaps..

       class role::redis_primary {
         realize Redis::Instance['core-redis', 'mobile-redis']
       }

This feels like a decent middle ground for us; it covers our use cases without too much additional complexity, and keeps (almost) all the config data in one place.

Branch Environments
-------------------

Tying VCS branches to Puppet environments is a common thing nowadays with [r10k](https://github.com/adrienthebo/r10k), but briefly for those not familiar..

 - Puppet nodes can have different environments, which ([in recent versions](https://docs.puppetlabs.com/puppet/latest/reference/environments.html#directory-environments-vs-config-file-environments)) mean different directories of manifests, modules, and hiera data on the master.  You can have a node temporarily or permanently report to a specific environment.
 - Having VCS branches map to these environments means that you can create a branch for any given change, large or small, and a Puppet environment will be created for it.  You can then have a node report to that branch for however long you need - weeks, one run, or even just a `--noop` run, to test the change before it goes live.

So, pretty much: it's incredibly useful.  Easy testing of expected behavior from changes, and we can use GitLab merge requests for getting more eye big changes and have the branch being reviewed be live configuration.

r10k does a great job of managing deploying the branch environments, as well as handling external module dependencies, but we're not using it; doing it right would mean switching each of our internal modules over to its own Git repo, which was just not worth the brain damage that would have incurred.

So instead, we just have a simple script that pulls from the gitlab repo, looks at its branches and deploys them (removing any branches that don't exist any more in git).

    #!/bin/bash -e

    #
    # teamcity_pull.sh 
    #

    # For parsing the git branch list..
    IFS=$'\n'

    # from http://stackoverflow.com/a/8574392
    containsElement () {
      local e
      for e in "${@:2}"; do [[ "$e" == "$1" ]] && return 0; done
      return 1
    }

    # Fetch new changes into shared repository
    # (this shared repo should have been cloned with 
    #  `git clone --mirror git@host:path/to/puppet.git`)
    cd /etc/puppet/puppet.git/
    git fetch -p

    # Get list of all branches (these should match remote after the fetch)
    branches=( $(git for-each-ref --format='%(refname:short)' refs/heads/) )

    cd /etc/puppet/environments/

    # For each branch that exists in the repo, verify that it's cloned (shared with the main repo)
    for branch in ${branches[@]}; do
      if [ -d "/etc/puppet/environments/${branch}" ]; then
        echo "${branch} branch and clone exist; pulling updates from shared repo"
        cd "/etc/puppet/environments/${branch}"
        git pull
        echo "${branch} decrypting blackbox.."
        BASEDIR="/etc/puppet/environments/${branch}" /usr/blackbox/bin/blackbox_postdeploy puppet
        cd /etc/puppet/environments/
      else
        echo "${branch} clone does not exist but should; cloning from shared repo"
        git clone --shared -b "${branch}" /etc/puppet/puppet.git "/etc/puppet/environments/${branch}"
        echo "${branch} decrypting blackbox.."
        BASEDIR="/etc/puppet/environments/${branch}" /usr/blackbox/bin/blackbox_postdeploy puppet
      fi
    done

    # Ignore the 'production' symlink from destruction..
    branches+=('production')

    # For each directory that exists in /etc/puppet/environments, verify that there's a
    # branch with that name.  If there is none, the branch is gone - nuke the environment.
    directories=( $(ls /etc/puppet/environments/) )

    # The containsElement function needs IFS to have spaces.
    IFS=' '
    for directory in ${directories[@]}; do
      if ! containsElement "${directory}" "${branches[@]}"; then
        echo "${directory} exists as a directory but is not a branch in the repo; rm -rf that sucka"
        rm -rf "/etc/puppet/environments/${directory}/"
      fi
    done

Pulling the Trigger
-------------------

With that all in place, we could start moving nodes over to the new masters.  Carefully, with `--noop` leading the way, and doing each node or role one-by-one.

Aside from a few permissions changes in `file` resources (ones that were picking up the permissions from the filesystem instead of in the manifest definition), most of the nodes applied their config against the new masters just as expected: with only changes to the `inifile` resources from the changes to `puppet.conf` - which is always a good feeling when applying 150 or so commits worth of change to these nodes all at once.

Once all the nodes were safely and healthily moved and looked good over a weekend, we moved the CA from the old master to one of the new ones (and set the param for the new master to get `ca = true` in `puppet.conf`), and turned the old masters off.

We threw up a boilerplate PuppetDB server in each location (with just a lazy Postgres backup/restore on a cron moving data between them), and got [PuppetBoard](https://github.com/nedap/puppetboard) running on top of that, which is a great modern web interface to get at the data in PuppetDB; some bits that Dashboard exposed aren't available because they aren't in the PuppetDB API, but it's getting there.

Down the Road
-------------

It's probably safe to say we'll always be working to improve the state of config management at Stack Exchange; some of the things we have on the roadmap to work on..

 - [Policy-based Autosigning](https://docs.puppetlabs.com/puppet/latest/reference/ssl_autosign.html#policy-based-autosigning) - we want for a node to come out of the build process and not need to be touched at all before applying the right config for it.  Current thinking is to have some kind of shared secret; the provisioning node can encrypt its hostname with the secret, stick that in a cert attribute, and the master can validate that encryption using a shared key then autosign the cert.
 - [module_data](https://forge.puppetlabs.com/ripienaar/module_data) - The [params pattern](https://docs.puppetlabs.com/guides/style_guide.html#class-parameter-defaults) is awful.  This module was originally proposed as a part of Puppet's core, allowing modules to have their own Hiera data, so they can have default params for certain OSes or versions - all fetched into class parameter lookups in the same way as your normal Hiera data.  We think this idea is great, and have a couple modules that are perfect use cases for it.  It might not be quite stable, but we're not shy about that.
 - PuppetDB replication is.. well, it isn't, really.  Right now it's just replication of the underlying Postgres though hot standby or backup/restore; there was a [plan presenteded at last year's PuppetConf](http://www.slideshare.net/PuppetLabs/puppetdb-new-adventures-in-higherorder-automation-puppetconf-2013) with replication features at the application level, but the [related issues](https://tickets.puppetlabs.com/browse/PDB-51) haven't gotten far, yet.  We'll be jumping on using this when it's released.
