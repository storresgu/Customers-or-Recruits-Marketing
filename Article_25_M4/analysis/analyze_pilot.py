"""Audit and summarize the registered Article 25 pilot without changing the model."""
import argparse,csv,hashlib,json,math,statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

def load(path): return json.loads(path.read_text())
def table(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))
def mean(x): return statistics.fmean(x) if x else None
def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def analyze(raw,prepared,out):
    out.mkdir(parents=True,exist_ok=False)
    manifest=load(raw/'manifest.json')
    assert manifest['status']=='completed' and manifest['completed_pairs']==manifest['planned_pairs']==40
    registry=load(raw/'run_registry.json'); expected=load(prepared/'run_registry.json')
    assert len(registry)==80 and all(r['status']=='completed' for r in registry)
    assert [{**r,'status':'planned'} for r in registry]==expected
    checked=0
    for name,h in manifest['files_sha256'].items():
        assert sha(raw/name)==h,(name,'hash mismatch')
        checked+=1
    runs=[]; monthly=[]; participants=[]; accounting_max_error=0.0
    for p in sorted((raw/'pairs').iterdir()):
        pm=load(p/'manifest.json')
        assert pm['status']=='completed' and pm['prefix_equality_checked'] and pm['zero_postshock_enrollment_checked']
        assert pm['code_hash']==manifest['code_hash']
        rows=table(p/'monthly_metrics.csv'); people=table(p/'participant_summary.csv')
        summaries=table(p/'run_summary.csv'); rm=load(p/'run_manifest.json')
        monthly.extend(rows);participants.extend(people)
        for summary,run_manifest in zip(summaries,rm):
            condition=summary['condition']; sid=summary['scenario_id']
            history=[r for r in rows if r['condition']==condition]
            cohort=[r for r in people if r['condition']==condition]
            assert [int(r['month']) for r in history]==list(range(1,121))
            assert all(sum(int(r['n_'+s]) for s in 'UCDI')==500 for r in history)
            if condition=='shock': assert sum(int(r['new_recruits']) for r in history[60:])==0
            last=history[-1]; active=[r for r in cohort if r['final_state']=='D']
            assert len(cohort)==int(last['n_D'])+int(last['n_I'])
            assert len(active)==int(last['n_D'])
            # Distinct accounting check: sum person cumulative cash vs every monthly cohort total.
            net_sum=math.fsum(float(r['cumulative_net_cash']) for r in cohort)
            monthly_net=math.fsum(float(r['net_cash_total']) for r in history)
            error=abs(net_sum-monthly_net);accounting_max_error=max(accounting_max_error,error)
            assert math.isclose(net_sum,monthly_net,abs_tol=1e-8,rel_tol=1e-10)
            assert math.isclose(net_sum,float(summary['all_ever_cumulative_net_total']),abs_tol=1e-8)
            for r in history:
                assert math.isclose(float(r['gross_earnings_total'])-float(r['expenses_total']),float(r['net_cash_total']),abs_tol=1e-8)
            late=history[108:120]
            def unused(channel):
                unused=sum(int(r['unused_'+channel+'_slots']) for r in late)
                used=sum(int(r[channel+'_contacts']) for r in late)
                return unused/(unused+used) if used+unused else None
            zero=[int(r['month']) for r in history if int(r['n_D'])==0]
            runs.append({
                'scenario_id':sid,'replicate_id':int(summary['replicate_id']),'pair_id':summary['pair_id'],
                'condition':condition,'seed':int(summary['seed']),
                'late_external_units':int(summary['late_external_units']),
                'late_external_retail_share':float(summary['late_external_retail_share']) if summary['late_external_retail_share'] else None,
                'final_U':int(last['n_U']),'final_C':int(last['n_C']),'final_D':int(last['n_D']),'final_I':int(last['n_I']),
                'extinct_at_120':bool(zero),'first_extinction_month':zero[0] if zero else None,
                'late_zero_external':int(summary['late_external_units'])==0,
                'ever_participants':len(cohort),'all_ever_median_net':float(summary['all_ever_cumulative_net_median']),
                'all_ever_loss_share':float(summary['all_ever_cumulative_net_loss_share']),
                'all_ever_gross_gini':float(summary['all_ever_cumulative_gross_gini']) if summary['all_ever_cumulative_gross_gini'] else None,
                'late_unused_retail_slot_share':unused('retail'),'late_unused_recruitment_slot_share':unused('recruitment'),
                'active_mean_eligible_retail_neighbors':mean([int(r['eligible_retail_neighbors_at_end']) for r in active]),
                'active_mean_eligible_recruitment_neighbors':mean([int(r['eligible_recruitment_neighbors_at_end']) for r in active]),
                'active_zero_recruitment_neighbors_share':mean([int(r['eligible_recruitment_neighbors_at_end'])==0 for r in active]),
                'prefix_seconds_shared':run_manifest['prefix_runtime_seconds_shared'],
                'branch_seconds':run_manifest['branch_runtime_seconds'],
            })
    effects=load(raw/'paired_effects.json')
    assert len(effects)==360 and len(monthly)==9600
    assert all(r['difference'] in (None,0) for r in effects if r['window']=='pre')
    scenarios=[]
    for sid in sorted({r['scenario_id'] for r in runs}):
        selected=[r for r in effects if r['scenario_id']==sid and r['window']=='late' and r['outcome']=='external_units']
        assert len(selected)==10
        differences=[r['difference'] for r in selected]; validratios=[r['resilience_ratio'] for r in selected if r['resilience_ratio'] is not None]
        cfg=next(r['config'] for r in registry if r['scenario_id']==sid)
        # Bootstrap resamples whole matched-pair differences, independently per scenario.
        bseed=int(hashlib.sha256(('article25-m4-bootstrap-v1:'+sid).encode()).hexdigest()[:8],16)
        means=np.random.default_rng(bseed).choice(differences,size=(20000,10),replace=True).mean(axis=1)
        lo,hi=np.quantile(means,[.025,.975])
        item={'scenario_id':sid,'p_retail':cfg['p_retail'],'p_repurchase':cfg['p_repurchase'],'pairs':10,
              'control_mean_late_external':mean([r['control'] for r in selected]),
              'shock_mean_late_external':mean([r['shock'] for r in selected]),
              'mean_paired_difference':mean(differences),'paired_difference_se':statistics.stdev(differences)/math.sqrt(10),
              'mean_difference_bootstrap_ci025':float(lo),'mean_difference_bootstrap_ci975':float(hi),
              'bootstrap_resamples':20000,'bootstrap_seed':bseed,
              'median_valid_resilience':statistics.median(validratios) if validratios else None,
              'undefined_resilience_pairs':10-len(validratios),'low_control_pairs':sum(r['low_control_external_volume'] for r in selected)}
        item['ratio_of_mean_volumes']=item['shock_mean_late_external']/item['control_mean_late_external'] if item['control_mean_late_external'] else None
        for condition in ('control','shock'):
            subset=[r for r in runs if r['scenario_id']==sid and r['condition']==condition]
            item[condition+'_extinctions']=sum(r['extinct_at_120'] for r in subset)
            item[condition+'_zero_late_external']=sum(r['late_zero_external'] for r in subset)
            for field in ('final_D','all_ever_loss_share','all_ever_median_net','late_unused_retail_slot_share',
                          'late_unused_recruitment_slot_share','active_mean_eligible_recruitment_neighbors'):
                item[condition+'_mean_'+field]=mean([r[field] for r in subset if r[field] is not None])
        scenarios.append(item)
    audit={'status':'passed','model_version':manifest['model_version'],'code_hash':manifest['code_hash'],
           'design_hash':manifest['design_hash'],'completed_pairs':40,'completed_branches':80,'monthly_rows':len(monthly),
           'participant_rows':len(participants),'paired_effect_rows':len(effects),'files_hash_verified':checked,
           'original_registry_unchanged':True,'all_preshock_differences_zero_when_defined':True,
           'zero_postshock_enrollment':True,'population_conservation_all_months':True,
           'max_cumulative_vs_monthly_cash_error':accounting_max_error,'runtime_seconds':manifest['runtime_seconds'],
           'raw_bytes':sum(p.stat().st_size for p in raw.rglob('*') if p.is_file()),
           'bootstrap_note':'Percentile CI for mean paired difference, 20000 whole-pair resamples; exploratory n=10 per scenario. Not a prediction interval.'}
    for name,rows in [('run_diagnostics',runs),('scenario_summary',scenarios),('monthly_metrics',monthly),('participant_summary',participants)]:
        write_csv(out/(name+'.csv'),rows)
    for name,data in [('audit',audit),('scenario_summary',scenarios)]:
        (out/(name+'.json')).write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'audit':audit,'scenarios':scenarios},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();analyze(a.raw,a.prepared,a.output)
