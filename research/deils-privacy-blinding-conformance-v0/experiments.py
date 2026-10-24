"""Synthetic privacy and tree-size experiments, separate from the DEILS reporter."""
import hashlib
import json
import rfc8785


def h(b):
    return hashlib.sha256(b).digest()


def privacy():
    # A deliberately tiny synthetic grid. Not actual user coordinates.
    candidates=[dict(latE7=x,lonE7=y,accuracyCm=25) for x in range(100,110) for y in range(-10,0)]
    chosen=candidates[42]
    target=h(rfc8785.dumps(chosen)).hex()
    matches=[i for i,c in enumerate(candidates) if h(rfc8785.dumps(c)).hex()==target]
    # Fixed published TEST nonce. The no-secret experiment does not hand it to the attacker.
    nonce='3f'*32
    blinded=h(rfc8785.dumps(dict(chosen,blinding=nonce))).hex()
    no_secret=[i for i,c in enumerate(candidates) if h(rfc8785.dumps(c)).hex()==blinded]
    # Disclosure control: the same attacker can recover the location if the nonce is available.
    disclosed=[i for i,c in enumerate(candidates) if h(rfc8785.dumps(dict(c,blinding=nonce))).hex()==blinded]
    return dict(candidates=len(candidates),unblinded_target=target,unblinded_matching_indices=matches,
                blinded_target=blinded,without_nonce_matching_indices=no_secret,
                disclosed_nonce_matching_indices=disclosed,
                tested_guesses_per_experiment=len(candidates),
                limitation='Finite candidate test only; secret unavailable is an experiment assumption, not a computational impossibility proof. All fixtures are public.')


def inclusion(leaf,index,size,path,root):
    """Independent bounded RFC9162 inclusion arithmetic, not an existing engine edit."""
    if size<=0 or index<0 or index>=size:return False
    fn,sn=index,size-1;r=h(b'\x00'+leaf)
    for sibling in path:
        if sn==0:return False
        if fn&1 or fn==sn:
            r=h(b'\x01'+sibling+r)
            while fn and not(fn&1):fn>>=1;sn>>=1
        else:r=h(b'\x01'+r+sibling)
        fn>>=1;sn>>=1
    return sn==0 and r==root


def tree_size():
    a,b,c=[h(b'\x00'+x) for x in [b'a',b'b',b'c']]
    root=h(b'\x01'+h(b'\x01'+a+b)+c)
    path=[b,c]
    # Authenticated OUT-OF-BAND selected checkpoint is a lab precondition, not self-authentication.
    selected=dict(batchId='synthetic-batch',treeHashProfile='RFC9162-SHA256-research',treeSize=3,root=root.hex())
    restated=dict(selected,treeSize=4)
    anchor=rfc8785.dumps(selected)
    return dict(root=root.hex(),proof_siblings=[x.hex() for x in path],leaf_hex=b'a'.hex(),leaf_index=0,
                actual_size=3,restated_size=4,
                root_only_actual=inclusion(b'a',0,3,path,root),
                root_only_restated=inclusion(b'a',0,4,path,root),
                wrong_root_control=inclusion(b'a',0,3,path,b'\x00'*32),
                size_bound_actual=rfc8785.dumps(selected)==anchor,
                size_bound_restated=rfc8785.dumps(restated)==anchor,
                anchor_canonical_utf8_hex=anchor.hex(),anchor_sha256=h(anchor).hex(),
                limitation='Authenticated selected bytes are independently configured laboratory input. No signature/publication/consensus authentication is established; not a new interoperable anchor profile.')


if __name__=='__main__':
    print(json.dumps(dict(privacy=privacy(),tree_size=tree_size()),sort_keys=True,indent=2))
